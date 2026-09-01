import os
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session
from decimal import Decimal
from .. import models, schemas
from ..database import get_db
from ..auth import get_current_user
from ..currency_utils import convert_amount

router = APIRouter(prefix="/currencies", tags=["currencies"])

@router.get("/rates", response_model=list[schemas.ExchangeRateOut])
def get_all_rates(db: Session = Depends(get_db)):
    return db.query(models.ExchangeRate).all()

@router.post("/rates", response_model=schemas.ExchangeRateOut)
def set_rate(payload: schemas.ExchangeRateSet, db: Session = Depends(get_db), x_admin_key: str = Header(...)):
    expected_key = os.getenv("ADMIN_TRIGGER_KEY")
    if not expected_key or x_admin_key != expected_key:
        raise HTTPException(status_code=403, detail="Неверный админ-ключ")

    existing = db.query(models.ExchangeRate).filter(
        models.ExchangeRate.currency_code == payload.currency_code
    ).first()

    if existing:
        existing.rate_to_rub = payload.rate_to_rub
    else:
        existing = models.ExchangeRate(currency_code=payload.currency_code, rate_to_rub=payload.rate_to_rub)
        db.add(existing)

    db.commit()
    db.refresh(existing)
    return existing

@router.get("/convert")
def convert(
    amount: Decimal = Query(...),
    from_currency: str = Query(..., alias="from"),
    to_currency: str = Query(..., alias="to"),
    db: Session = Depends(get_db),
):
    try:
        result = convert_amount(db, amount, from_currency, to_currency)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"original_amount": amount, "converted_amount": round(result, 2), "from": from_currency, "to": to_currency}