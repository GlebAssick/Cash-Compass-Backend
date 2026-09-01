from sqlalchemy import Column, Integer, String, DateTime, Numeric, ForeignKey, Enum, Date
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base
import enum

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    country = Column(String(2), nullable=False)
    education_level = Column(String(50), nullable=True)
    university = Column(String(150), nullable=True)
    base_currency = Column(String(3), nullable=False, default="RUB")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class TransactionType(str, enum.Enum):
    expense = "expense"
    income = "income"


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    is_default = Column(Integer, default=0)

    transactions = relationship("Transaction", back_populates="category")


class SpontaneousTag(str, enum.Enum):
    emotional = "emotional"      
    company = "company"            
    discount = "discount"          
    impulse = "impulse"             

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    type = Column(Enum(TransactionType), nullable=False, default=TransactionType.expense)
    description = Column(String(255), nullable=True)
    is_spontaneous = Column(Integer, default=0)
    tag = Column(Enum(SpontaneousTag), nullable=True)
    income_source_id = Column(Integer, ForeignKey("income_sources.id"), nullable=True)
    currency = Column(String(3), nullable=False, default="RUB")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    category = relationship("Category", back_populates="transactions")

class Budget(Base):
    __tablename__ = "budgets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True)
    monthly_amount = Column(Numeric(10, 2), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

from sqlalchemy import Date

class WeeklyBudget(Base):
    __tablename__ = "weekly_budgets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    week_amount = Column(Numeric(10, 2), nullable=False)
    week_start = Column(Date, nullable=False)
    week_end = Column(Date, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class RecurringExpense(Base):
    __tablename__ = "recurring_expenses"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    name = Column(String(100), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    day_of_month = Column(Integer, nullable=False)  # число месяца, когда списывается (1-28)
    is_active = Column(Integer, default=1)  # 1 = активна, 0 = отменена/приостановлена
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    country = Column(String(2), nullable=False)  # "RU" / "IN"
    name = Column(String(150), nullable=False)
    event_date = Column(Date, nullable=False)  # число и месяц, год не важен — событие повторяется ежегодно
    warning_message = Column(String(255), nullable=True)

class Goal(Base):
    __tablename__ = "goals"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(150), nullable=False)
    target_amount = Column(Numeric(10, 2), nullable=False)
    current_amount = Column(Numeric(10, 2), nullable=False, default=0)
    target_date = Column(Date, nullable=True)  # необязательный дедлайн
    is_completed = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class GoalContribution(Base):
    __tablename__ = "goal_contributions"

    id = Column(Integer, primary_key=True, index=True)
    goal_id = Column(Integer, ForeignKey("goals.id"), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    goal_id = Column(Integer, ForeignKey("goals.id"), nullable=True)
    message = Column(String(255), nullable=False)
    is_read = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class IncomeSource(Base):
    __tablename__ = "income_sources"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(100), nullable=False)  # "Стипендия", "Подработка", "Переводы от родителей"
    expected_amount = Column(Numeric(10, 2), nullable=True)  # ожидаемая сумма, если регулярная
    expected_day_of_month = Column(Integer, nullable=True)  # ожидаемое число месяца
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class ExchangeRate(Base):
    __tablename__ = "exchange_rates"

    id = Column(Integer, primary_key=True, index=True)
    currency_code = Column(String(3), nullable=False, unique=True)  # "RUB", "INR", "USD"
    rate_to_rub = Column(Numeric(10, 4), nullable=False)  # сколько рублей стоит 1 единица этой валюты
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())    

import secrets

class GroupGoal(Base):
    __tablename__ = "group_goals"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    target_amount = Column(Numeric(10, 2), nullable=False)
    current_amount = Column(Numeric(10, 2), nullable=False, default=0)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    invite_code = Column(String(16), unique=True, nullable=False, default=lambda: secrets.token_urlsafe(8))
    is_completed = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class GroupGoalMember(Base):
    __tablename__ = "group_goal_members"

    id = Column(Integer, primary_key=True, index=True)
    group_goal_id = Column(Integer, ForeignKey("group_goals.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    joined_at = Column(DateTime(timezone=True), server_default=func.now())


class GroupGoalContribution(Base):
    __tablename__ = "group_goal_contributions"

    id = Column(Integer, primary_key=True, index=True)
    group_goal_id = Column(Integer, ForeignKey("group_goals.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())    