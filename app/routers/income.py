from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import extract, func
from datetime import datetime, date
from decimal import Decimal
from .. import models, schemas
from ..database import get_db
from ..auth import get_current_user

router = APIRouter(prefix="/income", tags=["income"])

@router.get("/sources", response_model=list[schemas.IncomeSourceOut])
def get_income_sources(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return db.query(models.IncomeSource).filter(
        models.IncomeSource.user_id == current_user.id,
        models.IncomeSource.is_active == 1,
    ).all()

@router.post("/sources", response_model=schemas.IncomeSourceOut)
def create_income_source(payload: schemas.IncomeSourceCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    new_source = models.IncomeSource(
        user_id=current_user.id,
        name=payload.name,
        expected_amount=payload.expected_amount,
        expected_day_of_month=payload.expected_day_of_month,
        is_active=1,
    )
    db.add(new_source)
    db.commit()
    db.refresh(new_source)
    return new_source

@router.get("/anomalies")
def check_income_anomalies(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """Проверка: задержка регулярного дохода или падение суммы относительно среднего за 3 месяца"""
    today = date.today()
    sources = db.query(models.IncomeSource).filter(
        models.IncomeSource.user_id == current_user.id,
        models.IncomeSource.is_active == 1,
    ).all()

    anomalies = []

    for source in sources:
        # доход в этом месяце по этому источнику
        this_month_total = db.query(func.sum(models.Transaction.amount)).filter(
            models.Transaction.user_id == current_user.id,
            models.Transaction.income_source_id == source.id,
            extract("year", models.Transaction.created_at) == today.year,
            extract("month", models.Transaction.created_at) == today.month,
        ).scalar() or Decimal("0")

        # проверка задержки — если ожидаемый день уже прошёл, а дохода в этом месяце ещё нет
        if source.expected_day_of_month and today.day > source.expected_day_of_month and this_month_total == 0:
            days_late = today.day - source.expected_day_of_month
            anomalies.append({
                "source_id": source.id,
                "source_name": source.name,
                "type": "late",
                "message": f'"{source.name}" задерживается на {days_late} дн.'
            })

        # проверка падения суммы относительно среднего за последние 3 месяца (не считая текущий)
        avg_result = db.query(func.avg(models.Transaction.amount)).filter(
            models.Transaction.user_id == current_user.id,
            models.Transaction.income_source_id == source.id,
        ).scalar()

        if avg_result and this_month_total > 0:
            avg_amount = Decimal(str(avg_result))
            if this_month_total < avg_amount * Decimal("0.8"):  # упало более чем на 20%
                drop_percent = round(float((avg_amount - this_month_total) / avg_amount * 100), 1)
                anomalies.append({
                    "source_id": source.id,
                    "source_name": source.name,
                    "type": "amount_drop",
                    "message": f'"{source.name}" упал на {drop_percent}% относительно среднего.'
                })

    return {"anomalies": anomalies}