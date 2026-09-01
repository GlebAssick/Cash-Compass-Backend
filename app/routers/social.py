from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from datetime import datetime
from decimal import Decimal
from .. import models, schemas
from ..database import get_db
from ..auth import get_current_user
from ..currency_utils import convert_amount

router = APIRouter(prefix="/social", tags=["social"])

MIN_SAMPLE_SIZE = 3  # минимум пользователей в группе, чтобы показать статистику (защита анонимности)

def get_total_spent_for_users(db: Session, user_ids: list[int], year: int, month: int, target_currency: str) -> Decimal:
    if not user_ids:
        return Decimal("0")

    transactions = db.query(models.Transaction).filter(
        models.Transaction.user_id.in_(user_ids),
        models.Transaction.type == models.TransactionType.expense,
        extract("year", models.Transaction.created_at) == year,
        extract("month", models.Transaction.created_at) == month,
    ).all()

    total = Decimal("0")
    for tx in transactions:
        total += convert_amount(db, tx.amount, tx.currency, target_currency)
    return total

@router.get("/compare", response_model=schemas.SocialComparisonOut)
def compare_spending(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """
    Сравнивает траты текущего пользователя со средними тратами:
    - других студентов того же вуза
    - других студентов той же страны
    Показывает статистику, только если в группе достаточно людей (анонимность).
    """
    now = datetime.utcnow()

    # ваши траты
    your_total = get_total_spent_for_users(db, [current_user.id], now.year, now.month, current_user.base_currency)

    # группа "тот же вуз" (исключая себя)
    university_average = None
    university_sample = 0
    if current_user.university:
        university_users = db.query(models.User).filter(
            models.User.university == current_user.university,
            models.User.id != current_user.id,
        ).all()
        university_ids = [u.id for u in university_users]
        university_sample = len(university_ids)

        if university_sample >= MIN_SAMPLE_SIZE:
            total = get_total_spent_for_users(db, university_ids, now.year, now.month, current_user.base_currency)
            university_average = round(total / university_sample, 2)

    # группа "та же страна" (исключая себя)
    country_users = db.query(models.User).filter(
        models.User.country == current_user.country,
        models.User.id != current_user.id,
    ).all()
    country_ids = [u.id for u in country_users]
    country_sample = len(country_ids)

    country_average = None
    if country_sample >= MIN_SAMPLE_SIZE:
        total = get_total_spent_for_users(db, country_ids, now.year, now.month, current_user.base_currency)
        country_average = round(total / country_sample, 2)

    # формируем понятное сообщение
    if university_average is not None:
        diff_percent = round(float((your_total - university_average) / university_average * 100), 1) if university_average > 0 else 0
        if diff_percent > 0:
            message = f"Вы тратите на {abs(diff_percent)}% больше, чем в среднем студенты вашего вуза."
        elif diff_percent < 0:
            message = f"Вы тратите на {abs(diff_percent)}% меньше, чем в среднем студенты вашего вуза."
        else:
            message = "Ваши траты примерно совпадают со средними по вашему вузу."
    else:
        message = "Недостаточно данных для сравнения по вузу — попробуйте позже, когда больше студентов присоединится."

    return schemas.SocialComparisonOut(
        your_total=your_total,
        university_average=university_average,
        country_average=country_average,
        sample_size_university=university_sample,
        sample_size_country=country_sample,
        message=message,
    )