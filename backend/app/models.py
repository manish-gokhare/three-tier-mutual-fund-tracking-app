from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MutualFund(Base):
    __tablename__ = "mutual_funds"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    fund_name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    ticker_symbol: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    amfi_scheme_code: Mapped[str | None] = mapped_column(String(20), nullable=True, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FundNav(Base):
    __tablename__ = "fund_nav"
    __table_args__ = (UniqueConstraint("fund_id", "nav_date", name="uq_fund_nav_date"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    fund_id: Mapped[int] = mapped_column(ForeignKey("mutual_funds.id", ondelete="CASCADE"), nullable=False)
    nav_date: Mapped[date] = mapped_column(Date, nullable=False)
    nav: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    nav_source: Mapped[str] = mapped_column(String(20), nullable=False, server_default="seed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserHolding(Base):
    __tablename__ = "user_holdings"
    __table_args__ = (UniqueConstraint("user_id", "fund_id", name="uq_user_fund_holding"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    fund_id: Mapped[int] = mapped_column(ForeignKey("mutual_funds.id", ondelete="CASCADE"), nullable=False)
    units: Mapped[Decimal] = mapped_column(Numeric(16, 4), nullable=False)
    average_purchase_nav: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class NavSyncRun(Base):
    __tablename__ = "nav_sync_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    matched_funds: Mapped[int] = mapped_column(nullable=False, default=0)
    fetched_records: Mapped[int] = mapped_column(nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(nullable=True)
