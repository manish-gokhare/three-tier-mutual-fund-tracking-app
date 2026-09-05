from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class UserCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=255)


class UserRegister(UserCreate):
    password: str = Field(min_length=10, max_length=128)


class UserLogin(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: str
    created_at: datetime


class FundOut(BaseModel):
    id: int
    fund_name: str
    category: str
    ticker_symbol: str
    latest_nav: Decimal | None = None
    latest_nav_date: date | None = None
    latest_nav_source: str | None = None


class NavOut(BaseModel):
    nav_date: date
    nav: Decimal


class HoldingCreate(BaseModel):
    fund_id: int = Field(gt=0)
    units: Decimal = Field(gt=0, max_digits=16, decimal_places=4)
    average_purchase_nav: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=4)


class HoldingOut(BaseModel):
    id: int
    fund_id: int
    fund_name: str
    category: str
    ticker_symbol: str
    units: Decimal
    average_purchase_nav: Decimal | None
    latest_nav: Decimal | None
    current_value: Decimal | None
    invested_value: Decimal | None
    gain_loss: Decimal | None
    updated_at: datetime


class AuthOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class NavSyncStatus(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: str
    started_at: datetime
    completed_at: datetime | None
    matched_funds: int
    fetched_records: int
    error_message: str | None = None
