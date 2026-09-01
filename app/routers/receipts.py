from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from decimal import Decimal
from .. import models, schemas
from ..database import get_db
from ..auth import get_current_user
from ..claude_bot import parse_receipt_image

router = APIRouter(prefix="/receipts", tags=["receipts"])

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}

@router.post("/scan", response_model=schemas.ReceiptParseResult)
async def scan_receipt(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Поддерживаются только изображения JPEG, PNG или WEBP")

    image_bytes = await file.read()

    if len(image_bytes) > 5 * 1024 * 1024:  # 5 МБ лимит
        raise HTTPException(status_code=400, detail="Файл слишком большой (максимум 5 МБ)")

    result = parse_receipt_image(image_bytes, media_type=file.content_type)

    items = result.get("items", [])
    total = result.get("total", 0)
    source = result.get("source", "unavailable")

    return schemas.ReceiptParseResult(
        items=[schemas.ReceiptItem(**item) for item in items],
        total=Decimal(str(total)),
        source=source,
    )

@router.post("/confirm")
def confirm_receipt(
    payload: schemas.ReceiptConfirmRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Создаёт транзакции сразу по всем товарам из подтверждённого чека"""
    if not payload.items:
        raise HTTPException(status_code=400, detail="Список товаров пуст")

    created_transactions = []
    for item in payload.items:
        new_tx = models.Transaction(
            user_id=current_user.id,
            category_id=item.category_id,
            amount=item.amount,
            type=models.TransactionType.expense,
            description=item.name,
            is_spontaneous=0,
        )
        db.add(new_tx)
        created_transactions.append(new_tx)

    db.commit()

    for tx in created_transactions:
        db.refresh(tx)

    return {
        "created_count": len(created_transactions),
        "total_amount": sum((tx.amount for tx in created_transactions), Decimal("0")),
    }