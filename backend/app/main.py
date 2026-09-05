import os
from datetime import date, timedelta
from decimal import Decimal

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import case, func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .database import get_db, run_migrations
from .models import FundNav, MutualFund, NavSyncRun, User, UserHolding
from .schemas import (
    AuthOut,
    FundOut,
    HoldingCreate,
    HoldingOut,
    NavOut,
    NavSyncStatus,
    UserLogin,
    UserOut,
    UserRegister,
)
from .security import create_access_token, decode_access_token, hash_password, verify_password


app = FastAPI(title="Mutual Fund Tracker API", version="2.0.0")
origins = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
bearer_scheme = HTTPBearer(auto_error=False)


@app.on_event("startup")
def apply_migrations() -> None:
    run_migrations()


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication is required")
    user_id = decode_access_token(credentials.credentials)
    user = db.get(User, user_id) if user_id is not None else None
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session")
    return user


def require_owner(path_user_id: int, user: User) -> None:
    if path_user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only access your own portfolio")


def nav_priority():
    # Seed data is kept only as a fallback. Published AMFI data always wins.
    return case((FundNav.nav_source == "amfi", 1), else_=0).desc(), FundNav.nav_date.desc()


def latest_nav_value():
    return (
        select(FundNav.nav)
        .where(FundNav.fund_id == MutualFund.id)
        .order_by(*nav_priority())
        .limit(1)
        .scalar_subquery()
    )


def latest_nav_date():
    return (
        select(FundNav.nav_date)
        .where(FundNav.fund_id == MutualFund.id)
        .order_by(*nav_priority())
        .limit(1)
        .scalar_subquery()
    )


def latest_nav_source():
    return (
        select(FundNav.nav_source)
        .where(FundNav.fund_id == MutualFund.id)
        .order_by(*nav_priority())
        .limit(1)
        .scalar_subquery()
    )


def issue_token(user: User) -> AuthOut:
    return AuthOut(access_token=create_access_token(user.id), user=UserOut.model_validate(user))


@app.get("/health")
def healthcheck(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.post("/auth/register", response_model=AuthOut, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister, db: Session = Depends(get_db)):
    full_name = payload.full_name.strip()
    if not full_name:
        raise HTTPException(status_code=422, detail="Name cannot be blank")
    user = User(
        full_name=full_name,
        email=payload.email.strip().lower(),
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="An account with that email already exists")
    db.refresh(user)
    return issue_token(user)


@app.post("/auth/login", response_model=AuthOut)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email.strip().lower()))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    return issue_token(user)


@app.get("/auth/me", response_model=UserOut)
def get_me(user: User = Depends(current_user)):
    return user


@app.get("/funds", response_model=list[FundOut])
def list_funds(
    category: str | None = Query(default=None),
    search: str | None = Query(default=None, max_length=100),
    db: Session = Depends(get_db),
):
    nav = latest_nav_value()
    nav_date = latest_nav_date()
    nav_source = latest_nav_source()
    query = select(
        MutualFund,
        nav.label("latest_nav"),
        nav_date.label("latest_nav_date"),
        nav_source.label("latest_nav_source"),
    ).order_by(MutualFund.fund_name)
    if category:
        query = query.where(MutualFund.category.ilike(category.strip()))
    if search:
        pattern = f"%{search.strip()}%"
        query = query.where((MutualFund.fund_name.ilike(pattern)) | (MutualFund.ticker_symbol.ilike(pattern)))

    return [
        FundOut(
            id=fund.id,
            fund_name=fund.fund_name,
            category=fund.category,
            ticker_symbol=fund.ticker_symbol,
            latest_nav=current_nav,
            latest_nav_date=current_nav_date,
            latest_nav_source=current_nav_source,
        )
        for fund, current_nav, current_nav_date, current_nav_source in db.execute(query).all()
    ]


@app.get("/funds/{fund_id}/nav", response_model=list[NavOut])
def nav_history(
    fund_id: int,
    days: int = Query(default=30, ge=1, le=3650),
    db: Session = Depends(get_db),
):
    if db.get(MutualFund, fund_id) is None:
        raise HTTPException(status_code=404, detail="Fund not found")
    source = db.scalar(
        select(FundNav.nav_source).where(FundNav.fund_id == fund_id).order_by(*nav_priority()).limit(1)
    )
    if source is None:
        return []
    start_date = date.today() - timedelta(days=days - 1)
    query = (
        select(FundNav.nav_date, FundNav.nav)
        .where(FundNav.fund_id == fund_id, FundNav.nav_source == source, FundNav.nav_date >= start_date)
        .order_by(FundNav.nav_date.desc())
    )
    return [NavOut(nav_date=nav_date, nav=nav) for nav_date, nav in db.execute(query).all()]


@app.get("/nav-sync/status", response_model=NavSyncStatus | None)
def nav_sync_status(db: Session = Depends(get_db)):
    return db.scalar(select(NavSyncRun).order_by(NavSyncRun.started_at.desc()).limit(1))


def add_holding_for_user(user_id: int, payload: HoldingCreate, db: Session) -> HoldingOut:
    if db.get(MutualFund, payload.fund_id) is None:
        raise HTTPException(status_code=404, detail="Fund not found")

    statement = insert(UserHolding).values(
        user_id=user_id,
        fund_id=payload.fund_id,
        units=payload.units,
        average_purchase_nav=payload.average_purchase_nav,
    )
    combined_units = UserHolding.units + statement.excluded.units
    weighted_average = case(
        (statement.excluded.average_purchase_nav.is_(None), UserHolding.average_purchase_nav),
        (UserHolding.average_purchase_nav.is_(None), statement.excluded.average_purchase_nav),
        else_=(
            (UserHolding.units * UserHolding.average_purchase_nav)
            + (statement.excluded.units * statement.excluded.average_purchase_nav)
        )
        / combined_units,
    )
    statement = statement.on_conflict_do_update(
        constraint="uq_user_fund_holding",
        set_={
            "units": combined_units,
            "average_purchase_nav": weighted_average,
            "updated_at": func.now(),
        },
    ).returning(UserHolding.id)
    holding_id = db.execute(statement).scalar_one()
    db.commit()
    return get_holding(holding_id, user_id, db)


def get_holding(holding_id: int, user_id: int, db: Session) -> HoldingOut:
    nav = latest_nav_value()
    query = (
        select(UserHolding, MutualFund, nav.label("latest_nav"))
        .join(MutualFund, MutualFund.id == UserHolding.fund_id)
        .where(UserHolding.id == holding_id, UserHolding.user_id == user_id)
    )
    result = db.execute(query).one_or_none()
    if result is None:
        raise HTTPException(status_code=404, detail="Holding not found")
    holding, fund, current_nav = result
    invested_value = holding.units * holding.average_purchase_nav if holding.average_purchase_nav is not None else None
    current_value = holding.units * current_nav if current_nav is not None else None
    gain_loss = current_value - invested_value if current_value is not None and invested_value is not None else None
    return HoldingOut(
        id=holding.id,
        fund_id=fund.id,
        fund_name=fund.fund_name,
        category=fund.category,
        ticker_symbol=fund.ticker_symbol,
        units=holding.units,
        average_purchase_nav=holding.average_purchase_nav,
        latest_nav=current_nav,
        current_value=current_value,
        invested_value=invested_value,
        gain_loss=gain_loss,
        updated_at=holding.updated_at,
    )


def holdings_for_user(user: User, db: Session) -> list[HoldingOut]:
    holding_ids = db.scalars(
        select(UserHolding.id).where(UserHolding.user_id == user.id).order_by(UserHolding.updated_at.desc())
    ).all()
    return [get_holding(holding_id, user.id, db) for holding_id in holding_ids]


@app.post("/me/holdings", response_model=HoldingOut, status_code=status.HTTP_201_CREATED)
def add_my_holding(
    payload: HoldingCreate, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    return add_holding_for_user(user.id, payload, db)


@app.get("/me/holdings", response_model=list[HoldingOut])
def list_my_holdings(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return holdings_for_user(user, db)


# The user-id routes retain a conventional REST shape while preventing cross-user access.
@app.post("/users/{user_id}/holdings", response_model=HoldingOut, status_code=status.HTTP_201_CREATED)
def add_holding(
    user_id: int,
    payload: HoldingCreate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    require_owner(user_id, user)
    return add_holding_for_user(user_id, payload, db)


@app.get("/users/{user_id}/holdings", response_model=list[HoldingOut])
def list_holdings(user_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    require_owner(user_id, user)
    return holdings_for_user(user, db)
