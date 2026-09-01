from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from datetime import datetime, date
import calendar
from decimal import Decimal
from .. import models
from ..database import get_db
from ..auth import get_current_user
from ..routers.budget import build_budget_context
from ..financial_cards import get_relevant_cards

router = APIRouter(prefix="/cards", tags=["cards"])

def build_cards_context(db: Session, user: models.User) -> dict:
    now = datetime.utcnow()
    today = date.today()

    budget_context = build_budget_context(db, user)

    # разбивка расходов по категориям в процентах от общей суммы трат за месяц
    category_totals = db.query(
        models.Category.name,
        func.sum(models.Transaction.amount).label("total")
    ).join(
        models.Transaction, models.Transaction.category_id == models.Category.id
    ).filter(
        models.Transaction.user_id == user.id,
        models.Transaction.type == models.TransactionType.expense,
        extract("year", models.Transaction.created_at) == now.year,
        extract("month", models.Transaction.created_at) == now.month,
    ).group_by(models.Category.name).all()

    total_spent = sum((r.total for r in category_totals), Decimal("0"))
    category_percentages = {}
    if total_spent > 0:
        for r in category_totals:
            category_percentages[r.name] = float(r.total / total_spent * 100)

    # доля спонтанных трат
    spontaneous_total = db.query(func.sum(models.Transaction.amount)).filter(
        models.Transaction.user_id == user.id,
        models.Transaction.type == models.TransactionType.expense,
        models.Transaction.is_spontaneous == 1,
        extract("year", models.Transaction.created_at) == now.year,
        extract("month", models.Transaction.created_at) == now.month,
    ).scalar() or Decimal("0")
    spontaneous_percent = float(spontaneous_total / total_spent * 100) if total_spent > 0 else 0.0

    # количество активных подписок
    recurring_count = db.query(models.RecurringExpense).filter(
        models.RecurringExpense.user_id == user.id,
        models.RecurringExpense.is_active == 1,
    ).count()

    # есть ли хоть одна цель
    has_any_goal = db.query(models.Goal).filter(models.Goal.user_id == user.id).count() > 0

    # сколько месяцев пользователь уже пользуется приложением (грубо, по дате регистрации)
    months_of_data = max(1, (today.year - user.created_at.year) * 12 + (today.month - user.created_at.month))

    # какая доля месяца уже прошла
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    days_passed_ratio = today.day / days_in_month

    context = {
        "category_percentages": category_percentages,
        "spontaneous_percent": round(spontaneous_percent, 1),
        "recurring_count": recurring_count,
        "has_any_goal": has_any_goal,
        "months_of_data": months_of_data,
        "days_passed_ratio": round(days_passed_ratio, 2),
    }

    if budget_context:
        context["percent_used"] = budget_context["percent_used"]

    return context


@router.get("/relevant")
def get_relevant_financial_cards(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    context = build_cards_context(db, current_user)
    cards = get_relevant_cards(context)
    return {"cards": cards, "count": len(cards)}