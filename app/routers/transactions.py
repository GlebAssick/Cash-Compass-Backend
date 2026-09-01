from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .. import models, schemas
from ..database import get_db
from ..auth import get_current_user

router = APIRouter(prefix="/transactions", tags=["transactions"])

@router.get("/", response_model=list[schemas.TransactionOut])
def get_transactions(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return db.query(models.Transaction).filter(
        models.Transaction.user_id == current_user.id
    ).order_by(models.Transaction.created_at.desc()).all()

@router.post("/", response_model=schemas.TransactionOut)
def create_transaction(tx: schemas.TransactionCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    new_tx = models.Transaction(
        user_id=current_user.id,
        category_id=tx.category_id,
        amount=tx.amount,
        type=tx.type,
        description=tx.description,
        is_spontaneous=1 if tx.is_spontaneous else 0,
        tag=tx.tag,
        income_source_id=tx.income_source_id,
    )
    db.add(new_tx)
    db.commit()
    db.refresh(new_tx)
    return new_tx

@router.delete("/{tx_id}")
def delete_transaction(tx_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    tx = db.query(models.Transaction).filter(
        models.Transaction.id == tx_id, models.Transaction.user_id == current_user.id
    ).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Транзакция не найдена")
    db.delete(tx)
    db.commit()
    return {"detail": "Удалено"}

@router.put("/{tx_id}", response_model=schemas.TransactionOut)
def update_transaction(tx_id: int, tx_update: schemas.TransactionCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    tx = db.query(models.Transaction).filter(
        models.Transaction.id == tx_id, models.Transaction.user_id == current_user.id
    ).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Транзакция не найдена")

    tx.category_id = tx_update.category_id
    tx.amount = tx_update.amount
    tx.type = tx_update.type
    tx.description = tx_update.description
    tx.is_spontaneous = 1 if tx_update.is_spontaneous else 0
    tx.tag = tx_update.tag
    db.commit()
    db.refresh(tx)
    return tx

from sqlalchemy import func

@router.get("/spontaneous/stats")
def get_spontaneous_stats(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """Статистика по спонтанным тратам: сколько всего, по каким тегам, на какую сумму"""
    results = db.query(
        models.Transaction.tag,
        func.count(models.Transaction.id).label("count"),
        func.sum(models.Transaction.amount).label("total")
    ).filter(
        models.Transaction.user_id == current_user.id,
        models.Transaction.is_spontaneous == 1,
    ).group_by(models.Transaction.tag).all()

    return [
        {"tag": r.tag, "count": r.count, "total": r.total}
        for r in results
    ]