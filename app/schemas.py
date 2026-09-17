from pydantic import BaseModel, EmailStr, Field

class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    country: str
    education_level: str | None = None
    university: str | None = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

class VerifyEmailRequest(BaseModel):
    email: EmailStr
    code: str

class ResendVerificationRequest(BaseModel):
    email: EmailStr

class MessageResponse(BaseModel):
    message: str

class UserOut(BaseModel):
    id: int
    name: str | None
    email: EmailStr
    country: str
    education_level: str | None
    university: str | None
    base_currency: str
    is_verified: bool

    class Config:
        from_attributes = True

from decimal import Decimal
from datetime import datetime
from .models import TransactionType

class CategoryCreate(BaseModel):
    name: str

class CategoryOut(BaseModel):
    id: int
    name: str
    is_default: int

    class Config:
        from_attributes = True

from .models import SpontaneousTag

class TransactionCreate(BaseModel):
    category_id: int
    amount: Decimal
    type: TransactionType
    description: str | None = None
    is_spontaneous: bool = False
    tag: SpontaneousTag | None = None
    income_source_id: int | None = None
    currency: str | None = None  # если не указано — берётся базовая валюта пользователя

class TransactionOut(BaseModel):
    id: int
    category_id: int
    amount: Decimal
    type: TransactionType
    description: str | None
    is_spontaneous: int
    tag: SpontaneousTag | None
    income_source_id: int | None
    created_at: datetime

    class Config:
        from_attributes = True

    class Config:
        from_attributes = True

class BudgetSet(BaseModel):
    monthly_amount: Decimal

class BudgetOut(BaseModel):
    monthly_amount: Decimal
    spent: Decimal
    remaining: Decimal
    percent_used: float

    class Config:
        from_attributes = True

from datetime import date

class WeeklyBudgetCreate(BaseModel):
    week_amount: Decimal
    week_start: date | None = None  # если не указано — берём начало текущей недели

class WeeklyBudgetOut(BaseModel):
    week_amount: Decimal
    week_start: date
    week_end: date
    spent: Decimal
    remaining: Decimal

    class Config:
        from_attributes = True

class RecurringExpenseCreate(BaseModel):
    category_id: int
    name: str
    amount: Decimal
    day_of_month: int = Field(ge=1, le=28)

class RecurringExpenseOut(BaseModel):
    id: int
    category_id: int
    name: str
    amount: Decimal
    day_of_month: int
    is_active: int

    class Config:
        from_attributes = True

class EventOut(BaseModel):
    id: int
    country: str
    name: str
    event_date: date
    warning_message: str | None

    class Config:
        from_attributes = True

class GoalCreate(BaseModel):
    name: str
    target_amount: Decimal
    target_date: date | None = None

class GoalOut(BaseModel):
    id: int
    name: str
    target_amount: Decimal
    current_amount: Decimal
    target_date: date | None
    is_completed: int
    progress_percent: float

    class Config:
        from_attributes = True

class GoalContributionCreate(BaseModel):
    amount: Decimal

class NotificationOut(BaseModel):
    id: int
    goal_id: int | None
    message: str
    is_read: int
    created_at: datetime

    class Config:
        from_attributes = True

class IncomeSourceCreate(BaseModel):
    name: str
    expected_amount: Decimal | None = None
    expected_day_of_month: int | None = Field(default=None, ge=1, le=28)

class IncomeSourceOut(BaseModel):
    id: int
    name: str
    expected_amount: Decimal | None
    expected_day_of_month: int | None
    is_active: int

    class Config:
        from_attributes = True


class ReceiptItem(BaseModel):
    name: str
    amount: Decimal
    suggested_category: str | None = None

class ReceiptParseResult(BaseModel):
    items: list[ReceiptItem]
    total: Decimal
    source: str  # "claude_vision" или "unavailable"

class ReceiptConfirmItem(BaseModel):
    name: str
    amount: Decimal
    category_id: int

class ReceiptConfirmRequest(BaseModel):
    items: list[ReceiptConfirmItem]

class BankTransactionPreview(BaseModel):
    date: str
    description: str
    amount: Decimal
    type: TransactionType
    suggested_category_id: int | None = None

class BankImportPreviewResult(BaseModel):
    transactions: list[BankTransactionPreview]
    total_count: int

class BankImportConfirmItem(BaseModel):
    description: str
    amount: Decimal
    type: TransactionType
    category_id: int

class BankImportConfirmRequest(BaseModel):
    items: list[BankImportConfirmItem]    

class ExchangeRateOut(BaseModel):
    currency_code: str
    rate_to_rub: Decimal

    class Config:
        from_attributes = True

class ExchangeRateSet(BaseModel):
    currency_code: str
    rate_to_rub: Decimal    

class SocialComparisonOut(BaseModel):
    your_total: Decimal
    university_average: Decimal | None
    country_average: Decimal | None
    sample_size_university: int
    sample_size_country: int
    message: str

class GroupGoalCreate(BaseModel):
    name: str
    target_amount: Decimal

class GroupGoalMemberOut(BaseModel):
    user_id: int
    email: str
    contributed: Decimal

class GroupGoalOut(BaseModel):
    id: int
    name: str
    target_amount: Decimal
    current_amount: Decimal
    invite_code: str
    is_completed: int
    progress_percent: float
    members: list[GroupGoalMemberOut] = []

    class Config:
        from_attributes = True

class GroupGoalJoin(BaseModel):
    invite_code: str

class GroupGoalContributeRequest(BaseModel):
    amount: Decimal        