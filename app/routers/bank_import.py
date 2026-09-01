from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from decimal import Decimal
from .. import models, schemas
from ..database import get_db
from ..auth import get_current_user
from ..bank_parser import parse_csv_statement, parse_pdf_statement

router = APIRouter(prefix="/bank-import", tags=["bank-import"])

@router.post("/csv", response_model=schemas.BankImportPreviewResult)
async def import_csv_statement(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Ожидается файл формата .csv")

    file_bytes = await file.read()

    try:
        parsed = parse_csv_statement(file_bytes, db, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Не удалось обработать файл: {e}")

    return schemas.BankImportPreviewResult(
        transactions=[schemas.BankTransactionPreview(**tx) for tx in parsed],
        total_count=len(parsed),
    )

@router.post("/confirm")
def confirm_bank_import(
    payload: schemas.BankImportConfirmRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    if not payload.items:
        raise HTTPException(status_code=400, detail="Список транзакций пуст")

    created = []
    for item in payload.items:
        new_tx = models.Transaction(
            user_id=current_user.id,
            category_id=item.category_id,
            amount=item.amount,
            type=item.type,
            description=item.description,
        )
        db.add(new_tx)
        created.append(new_tx)

    db.commit()

    return {
        "created_count": len(created),
        "total_amount": sum((tx.amount for tx in created), Decimal("0")),
    }


@router.post("/pdf", response_model=schemas.BankImportPreviewResult)
async def import_pdf_statement(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Ожидается файл формата .pdf")

    file_bytes = await file.read()

    try:
        parsed = parse_pdf_statement(file_bytes, db, current_user.id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Не удалось обработать файл: {e}")

    if not parsed:
        raise HTTPException(
            status_code=422,
            detail="Не удалось распознать транзакции в этом PDF. Формат выписки может отличаться от ожидаемого."
        )

    return schemas.BankImportPreviewResult(
        transactions=[schemas.BankTransactionPreview(**tx) for tx in parsed],
        total_count=len(parsed),
    )