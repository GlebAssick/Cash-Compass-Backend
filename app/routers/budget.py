from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from datetime import datetime
from decimal import Decimal
from .. import models, schemas
from ..database import get_db
from ..auth import get_current_user
from datetime import date, timedelta
from datetime import date
import calendar

router = APIRouter(prefix="/budget", tags=["budget"])

from ..currency_utils import convert_amount

def calculate_spent_this_month(db: Session, user_id: int) -> Decimal:
    now = datetime.utcnow()
    user = db.query(models.User).filter(models.User.id == user_id).first()

    transactions = db.query(models.Transaction).filter(
        models.Transaction.user_id == user_id,
        models.Transaction.type == models.TransactionType.expense,
        extract("year", models.Transaction.created_at) == now.year,
        extract("month", models.Transaction.created_at) == now.month,
    ).all()

    total = Decimal("0")
    for tx in transactions:
        total += convert_amount(db, tx.amount, tx.currency, user.base_currency)
    return total

@router.post("/", response_model=schemas.BudgetOut)
def set_budget(budget: schemas.BudgetSet, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    existing = db.query(models.Budget).filter(models.Budget.user_id == current_user.id).first()
    if existing:
        existing.monthly_amount = budget.monthly_amount
    else:
        existing = models.Budget(user_id=current_user.id, monthly_amount=budget.monthly_amount)
        db.add(existing)
    db.commit()
    db.refresh(existing)

    spent = calculate_spent_this_month(db, current_user.id)
    remaining = existing.monthly_amount - spent
    percent = float(spent / existing.monthly_amount * 100) if existing.monthly_amount > 0 else 0.0

    return schemas.BudgetOut(
        monthly_amount=existing.monthly_amount,
        spent=spent,
        remaining=remaining,
        percent_used=round(percent, 1),
    )

@router.get("/", response_model=schemas.BudgetOut)
def get_budget(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    budget = db.query(models.Budget).filter(models.Budget.user_id == current_user.id).first()
    if not budget:
        raise HTTPException(status_code=404, detail="Бюджет ещё не задан")

    spent = calculate_spent_this_month(db, current_user.id)
    remaining = budget.monthly_amount - spent
    percent = float(spent / budget.monthly_amount * 100) if budget.monthly_amount > 0 else 0.0

    return schemas.BudgetOut(
        monthly_amount=budget.monthly_amount,
        spent=spent,
        remaining=remaining,
        percent_used=round(percent, 1),
    )

def get_current_week_range() -> tuple[date, date]:
    today = date.today()
    start = today - timedelta(days=today.weekday())  # понедельник этой недели
    end = start + timedelta(days=6)  # воскресенье
    return start, end

def calculate_allocated_this_month(db: Session, user_id: int, exclude_id: int | None = None) -> Decimal:
    """Сумма всех недельных бюджетов, чья неделя началась в текущем месяце"""
    now = datetime.utcnow()
    query = db.query(func.sum(models.WeeklyBudget.week_amount)).filter(
        models.WeeklyBudget.user_id == user_id,
        extract("year", models.WeeklyBudget.week_start) == now.year,
        extract("month", models.WeeklyBudget.week_start) == now.month,
    )
    if exclude_id:
        query = query.filter(models.WeeklyBudget.id != exclude_id)
    result = query.scalar()
    return result or Decimal("0")

@router.post("/weekly", response_model=schemas.WeeklyBudgetOut)
def set_weekly_budget(payload: schemas.WeeklyBudgetCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    monthly_budget = db.query(models.Budget).filter(models.Budget.user_id == current_user.id).first()
    if not monthly_budget:
        raise HTTPException(status_code=400, detail="Сначала задайте месячный бюджет")

    week_start = payload.week_start or get_current_week_range()[0]
    week_end = week_start + timedelta(days=6)

    spent_this_month = calculate_spent_this_month(db, current_user.id)
    allocated_this_month = calculate_allocated_this_month(db, current_user.id)
    monthly_remaining = monthly_budget.monthly_amount - spent_this_month - allocated_this_month

    if payload.week_amount > monthly_remaining:
        raise HTTPException(
            status_code=400,
            detail=f"Недостаточно средств в месячном бюджете. Доступно: {monthly_remaining} руб."
        )

    new_weekly = models.WeeklyBudget(
        user_id=current_user.id,
        week_amount=payload.week_amount,
        week_start=week_start,
        week_end=week_end,
    )
    db.add(new_weekly)
    db.commit()
    db.refresh(new_weekly)

    return schemas.WeeklyBudgetOut(
        week_amount=new_weekly.week_amount,
        week_start=new_weekly.week_start,
        week_end=new_weekly.week_end,
        spent=Decimal("0"),
        remaining=new_weekly.week_amount,
    )

@router.get("/weekly/current", response_model=schemas.WeeklyBudgetOut)
def get_current_weekly_budget(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    week_start, week_end = get_current_week_range()

    weekly = db.query(models.WeeklyBudget).filter(
        models.WeeklyBudget.user_id == current_user.id,
        models.WeeklyBudget.week_start == week_start,
    ).first()

    if not weekly:
        raise HTTPException(status_code=404, detail="Недельный бюджет на эту неделю ещё не задан")

    spent = db.query(func.sum(models.Transaction.amount)).filter(
        models.Transaction.user_id == current_user.id,
        models.Transaction.type == models.TransactionType.expense,
        func.date(models.Transaction.created_at) >= weekly.week_start,
        func.date(models.Transaction.created_at) <= weekly.week_end,
    ).scalar() or Decimal("0")

    remaining = weekly.week_amount - spent

    return schemas.WeeklyBudgetOut(
        week_amount=weekly.week_amount,
        week_start=weekly.week_start,
        week_end=weekly.week_end,
        spent=spent,
        remaining=remaining,
    )

@router.get("/forecast")
def get_budget_forecast(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """Прогноз: на сколько дней хватит бюджета при текущем темпе трат"""
    budget = db.query(models.Budget).filter(models.Budget.user_id == current_user.id).first()
    if not budget:
        raise HTTPException(status_code=404, detail="Бюджет ещё не задан")

    today = date.today()
    days_passed = today.day
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    days_remaining_in_month = days_in_month - days_passed

    spent = calculate_spent_this_month(db, current_user.id)
    remaining = budget.monthly_amount - spent

    if spent <= 0 or days_passed == 0:
        return {
            "status": "not_enough_data",
            "message": "Пока недостаточно данных о тратах в этом месяце для прогноза."
        }

    daily_average = spent / days_passed

    if daily_average <= 0:
        return {
            "status": "on_track",
            "message": "Расходов пока нет — бюджет точно хватит до конца месяца."
        }

    days_budget_will_last = float(remaining / daily_average)

    if days_budget_will_last >= days_remaining_in_month:
        surplus_days = round(days_budget_will_last - days_remaining_in_month, 1)
        return {
            "status": "on_track",
            "daily_average": round(float(daily_average), 2),
            "message": f"При текущем темпе бюджета хватит с запасом на {surplus_days} дн. дольше, чем нужно."
        }
    else:
        run_out_date = today + timedelta(days=int(days_budget_will_last))
        days_short = round(days_remaining_in_month - days_budget_will_last, 1)
        return {
            "status": "will_run_out",
            "daily_average": round(float(daily_average), 2),
            "estimated_run_out_date": str(run_out_date),
            "message": f"При текущем темпе бюджет закончится {run_out_date.strftime('%d.%m')}, за {days_short:.0f} дн. до конца месяца."
        }

def build_budget_context(db: Session, user: models.User) -> dict | None:
    """Возвращает контекст бюджета пользователя, или None если бюджет не задан"""
    budget = db.query(models.Budget).filter(models.Budget.user_id == user.id).first()
    if not budget:
        return None

    spent = calculate_spent_this_month(db, user.id)
    remaining = budget.monthly_amount - spent
    percent = float(spent / budget.monthly_amount * 100) if budget.monthly_amount > 0 else 0.0

    return {
        "monthly_amount": budget.monthly_amount,
        "spent": spent,
        "remaining": remaining,
        "percent_used": round(percent, 1),
    }    