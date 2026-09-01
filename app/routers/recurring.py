from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from decimal import Decimal
from .. import models, schemas
from ..database import get_db
from ..auth import get_current_user
from sqlalchemy import extract, func as sqlfunc
from datetime import datetime

router = APIRouter(prefix="/recurring", tags=["recurring"])

@router.get("/", response_model=list[schemas.RecurringExpenseOut])
def get_recurring_expenses(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return db.query(models.RecurringExpense).filter(
        models.RecurringExpense.user_id == current_user.id,
        models.RecurringExpense.is_active == 1,
    ).all()

@router.post("/", response_model=schemas.RecurringExpenseOut)
def create_recurring_expense(payload: schemas.RecurringExpenseCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    new_recurring = models.RecurringExpense(
        user_id=current_user.id,
        category_id=payload.category_id,
        name=payload.name,
        amount=payload.amount,
        day_of_month=payload.day_of_month,
        is_active=1,
    )
    db.add(new_recurring)
    db.commit()
    db.refresh(new_recurring)
    return new_recurring

@router.delete("/{recurring_id}")
def deactivate_recurring_expense(recurring_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    recurring = db.query(models.RecurringExpense).filter(
        models.RecurringExpense.id == recurring_id,
        models.RecurringExpense.user_id == current_user.id,
    ).first()
    if not recurring:
        raise HTTPException(status_code=404, detail="Подписка не найдена")

    recurring.is_active = 0
    db.commit()
    return {"detail": "Подписка отменена"}

@router.get("/monthly-total")
def get_monthly_recurring_total(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """Сколько всего уходит на регулярные платежи в месяц — для прогноза и планирования"""
    recurring = db.query(models.RecurringExpense).filter(
        models.RecurringExpense.user_id == current_user.id,
        models.RecurringExpense.is_active == 1,
    ).all()
    total = sum((r.amount for r in recurring), Decimal("0"))
    return {"monthly_total": total, "count": len(recurring)}

@router.get("/waste-detection")
def detect_wasteful_subscriptions(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """
    Ищет два типа проблем:
    1. Дублирующиеся активные подписки (похожие названия — возможно, оформили дважды)
    2. Регулярные транзакции, которые платятся, но НЕ зарегистрированы как recurring_expense
       (то есть пользователь платит за что-то каждый месяц вручную, не замечая паттерна)
    """
    active_recurring = db.query(models.RecurringExpense).filter(
        models.RecurringExpense.user_id == current_user.id,
        models.RecurringExpense.is_active == 1,
    ).all()

    findings = []

    # --- Проверка 1: дублирующиеся подписки по похожему названию ---
    seen_names = {}
    for r in active_recurring:
        normalized = r.name.strip().lower()
        if normalized in seen_names:
            findings.append({
                "type": "duplicate_subscription",
                "message": f'Найдены две активные подписки с похожим названием: "{seen_names[normalized]}" и "{r.name}". Возможно, одна из них лишняя.',
                "recurring_ids": [seen_names[normalized + "_id"], r.id] if normalized + "_id" in seen_names else [r.id],
            })
        seen_names[normalized] = r.name
        seen_names[normalized + "_id"] = r.id

    # --- Проверка 2: похожие на подписку транзакции, не оформленные как recurring ---
    three_months_ago = datetime.utcnow().replace(day=1)
    recent_transactions = db.query(models.Transaction).filter(
        models.Transaction.user_id == current_user.id,
        models.Transaction.type == models.TransactionType.expense,
        models.Transaction.income_source_id.is_(None),
    ).order_by(models.Transaction.created_at.desc()).limit(200).all()

    registered_names = {r.name.strip().lower() for r in active_recurring}

    description_groups: dict[str, list] = {}
    for tx in recent_transactions:
        if not tx.description:
            continue
        key = tx.description.strip().lower()
        description_groups.setdefault(key, []).append(tx)

    for description, txs in description_groups.items():
        if len(txs) >= 3 and description not in registered_names:
            amounts = {float(t.amount) for t in txs}
            if len(amounts) == 1:  # одинаковая сумма каждый раз — характерно для подписок
                findings.append({
                    "type": "unregistered_recurring_pattern",
                    "message": f'Вы регулярно платите "{txs[0].description}" одинаковую сумму ({txs[0].amount} руб.) — похоже на подписку. Добавить в регулярные платежи?',
                    "suggested_amount": txs[0].amount,
                    "suggested_name": txs[0].description,
                    "occurrences": len(txs),
                })

    return {"findings": findings, "count": len(findings)}
