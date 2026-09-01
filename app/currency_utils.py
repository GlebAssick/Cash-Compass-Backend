from decimal import Decimal
from sqlalchemy.orm import Session
from . import models

def get_rate_to_rub(db: Session, currency_code: str) -> Decimal:
    if currency_code == "RUB":
        return Decimal("1")

    rate = db.query(models.ExchangeRate).filter(
        models.ExchangeRate.currency_code == currency_code
    ).first()
    if not rate:
        raise ValueError(f"Курс для валюты {currency_code} не найден")
    return rate.rate_to_rub

def convert_amount(db: Session, amount: Decimal, from_currency: str, to_currency: str) -> Decimal:
    if from_currency == to_currency:
        return amount

    rate_from = get_rate_to_rub(db, from_currency)
    rate_to = get_rate_to_rub(db, to_currency)

    amount_in_rub = amount * rate_from
    return amount_in_rub / rate_to