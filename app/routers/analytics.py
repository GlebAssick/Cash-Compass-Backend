from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from datetime import datetime, date, timedelta
from decimal import Decimal
from .. import models
from ..database import get_db
from ..auth import get_current_user

router = APIRouter(prefix="/analytics", tags=["analytics"])

@router.get("/by-category")
def get_spending_by_category(
    year: int = Query(default=None),
    month: int = Query(default=None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Сумма расходов по каждой категории за указанный месяц (по умолчанию текущий)"""
    now = datetime.utcnow()
    target_year = year or now.year
    target_month = month or now.month

    results = db.query(
        models.Category.id,
        models.Category.name,
        func.sum(models.Transaction.amount).label("total")
    ).join(
        models.Transaction, models.Transaction.category_id == models.Category.id
    ).filter(
        models.Transaction.user_id == current_user.id,
        models.Transaction.type == models.TransactionType.expense,
        extract("year", models.Transaction.created_at) == target_year,
        extract("month", models.Transaction.created_at) == target_month,
    ).group_by(models.Category.id, models.Category.name).all()

    return [
        {"category_id": r.id, "category_name": r.name, "total": r.total}
        for r in results
    ]

@router.get("/daily")
def get_daily_spending(
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Сумма расходов по дням за последние N дней — для линейного графика"""
    start_date = date.today() - timedelta(days=days)

    results = db.query(
        func.date(models.Transaction.created_at).label("day"),
        func.sum(models.Transaction.amount).label("total")
    ).filter(
        models.Transaction.user_id == current_user.id,
        models.Transaction.type == models.TransactionType.expense,
        func.date(models.Transaction.created_at) >= start_date,
    ).group_by(func.date(models.Transaction.created_at)).order_by("day").all()

    return [
        {"date": str(r.day), "total": r.total}
        for r in results
    ]

@router.get("/summary")
def get_summary(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Общая сводка: доходы/расходы за текущий месяц"""
    now = datetime.utcnow()

    expense_total = db.query(func.sum(models.Transaction.amount)).filter(
        models.Transaction.user_id == current_user.id,
        models.Transaction.type == models.TransactionType.expense,
        extract("year", models.Transaction.created_at) == now.year,
        extract("month", models.Transaction.created_at) == now.month,
    ).scalar() or Decimal("0")

    income_total = db.query(func.sum(models.Transaction.amount)).filter(
        models.Transaction.user_id == current_user.id,
        models.Transaction.type == models.TransactionType.income,
        extract("year", models.Transaction.created_at) == now.year,
        extract("month", models.Transaction.created_at) == now.month,
    ).scalar() or Decimal("0")

    return {
        "total_expense": expense_total,
        "total_income": income_total,
        "net": income_total - expense_total,
    }

@router.get("/month-comparison")
def get_month_comparison(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Сравнение расходов по категориям: текущий месяц vs предыдущий"""
    now = datetime.utcnow()

    # текущий месяц
    current_year, current_month = now.year, now.month

    # предыдущий месяц (учитываем переход через январь)
    if current_month == 1:
        prev_year, prev_month = current_year - 1, 12
    else:
        prev_year, prev_month = current_year, current_month - 1

    def get_totals_by_category(year: int, month: int):
        results = db.query(
            models.Category.id,
            models.Category.name,
            func.sum(models.Transaction.amount).label("total")
        ).join(
            models.Transaction, models.Transaction.category_id == models.Category.id
        ).filter(
            models.Transaction.user_id == current_user.id,
            models.Transaction.type == models.TransactionType.expense,
            extract("year", models.Transaction.created_at) == year,
            extract("month", models.Transaction.created_at) == month,
        ).group_by(models.Category.id, models.Category.name).all()
        return {r.id: {"name": r.name, "total": r.total} for r in results}

    current_data = get_totals_by_category(current_year, current_month)
    prev_data = get_totals_by_category(prev_year, prev_month)

    all_category_ids = set(current_data.keys()) | set(prev_data.keys())

    comparison = []
    for cat_id in all_category_ids:
        current_total = current_data.get(cat_id, {}).get("total", Decimal("0"))
        prev_total = prev_data.get(cat_id, {}).get("total", Decimal("0"))
        name = current_data.get(cat_id, {}).get("name") or prev_data.get(cat_id, {}).get("name")

        if prev_total > 0:
            percent_change = float((current_total - prev_total) / prev_total * 100)
        else:
            percent_change = 100.0 if current_total > 0 else 0.0

        comparison.append({
            "category_id": cat_id,
            "category_name": name,
            "current_month_total": current_total,
            "previous_month_total": prev_total,
            "percent_change": round(percent_change, 1),
        })

    comparison.sort(key=lambda x: abs(x["percent_change"]), reverse=True)

    return {
        "current_month": f"{current_year}-{current_month:02d}",
        "previous_month": f"{prev_year}-{prev_month:02d}",
        "categories": comparison,
    }