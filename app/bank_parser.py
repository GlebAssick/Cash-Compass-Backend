import pandas as pd
import io
from decimal import Decimal
from sqlalchemy.orm import Session
from . import models
import pdfplumber
import re

# Ключевые слова для авто-категоризации по описанию транзакции
CATEGORY_KEYWORDS = {
    "Еда": ["магазин", "продукты", "супермаркет", "кафе", "ресторан", "пятерочка", "магнит", "перекресток"],
    "Транспорт": ["метро", "такси", "автобус", "яндекс.такси", "uber", "бензин", "азс"],
    "Жильё": ["аренда", "квартплата", "коммунал", "жкх"],
    "Развлечения": ["кино", "театр", "netflix", "spotify", "steam", "playstation"],
    "Здоровье": ["аптека", "клиника", "больница", "врач"],
}

def guess_category_id(db: Session, user_id: int, description: str) -> int | None:
    """Пытается угадать категорию по ключевым словам в описании транзакции"""
    description_lower = description.lower()

    for category_name, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in description_lower for keyword in keywords):
            category = db.query(models.Category).filter(
                models.Category.name == category_name,
                models.Category.is_default == 1,
            ).first()
            if category:
                return category.id

    # если ничего не подошло — категория "Прочее"
    fallback = db.query(models.Category).filter(
        models.Category.name == "Прочее",
        models.Category.is_default == 1,
    ).first()
    return fallback.id if fallback else None


def parse_csv_statement(file_bytes: bytes, db: Session, user_id: int) -> list[dict]:
    """
    Ожидаемый формат CSV: колонки date, description, amount
    (amount отрицательный = расход, положительный = доход — частый стандарт у банков)
    """
    df = pd.read_csv(io.BytesIO(file_bytes))

    df.columns = [c.strip().lower() for c in df.columns]
    required_columns = {"date", "description", "amount"}
    if not required_columns.issubset(set(df.columns)):
        raise ValueError(f"CSV должен содержать колонки: {required_columns}. Найдены: {list(df.columns)}")

    results = []
    for _, row in df.iterrows():
        amount = Decimal(str(row["amount"]))
        tx_type = models.TransactionType.income if amount > 0 else models.TransactionType.expense
        description = str(row["description"])

        results.append({
            "date": str(row["date"]),
            "description": description,
            "amount": abs(amount),
            "type": tx_type,
            "suggested_category_id": guess_category_id(db, user_id, description) if tx_type == models.TransactionType.expense else None,
        })

    return results

# Паттерн строки транзакции в большинстве банковских PDF-выписок:
# дата, описание, сумма (пример: "15.08.2026  Продукты Пятерочка  -450.00")
TRANSACTION_LINE_PATTERN = re.compile(
    r"(\d{2}\.\d{2}\.\d{4})\s+(.+?)\s+(-?\d+[.,]\d{2})"
)

def parse_pdf_statement(file_bytes: bytes, db: Session, user_id: int) -> list[dict]:
    results = []

    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            for line in text.split("\n"):
                match = TRANSACTION_LINE_PATTERN.search(line)
                if not match:
                    continue

                date_str, description, amount_str = match.groups()
                amount_str = amount_str.replace(",", ".")
                amount = Decimal(amount_str)

                tx_type = models.TransactionType.income if amount > 0 else models.TransactionType.expense
                description = description.strip()

                results.append({
                    "date": date_str,
                    "description": description,
                    "amount": abs(amount),
                    "type": tx_type,
                    "suggested_category_id": guess_category_id(db, user_id, description) if tx_type == models.TransactionType.expense else None,
                })

    return results