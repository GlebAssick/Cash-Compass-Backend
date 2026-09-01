from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import engine, Base, SessionLocal
from .import models
from .routers import auth, categories, transactions, budget, bot, recurring, analytics, events, goals, notifications, income, receipts, bank_import, currency, social, cards, group_goals
app = FastAPI(title="Cash Compass API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # на этапе разработки разрешаем всем, сузим перед финальным релизом
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(categories.router, prefix="/api/v1")
app.include_router(transactions.router, prefix="/api/v1")
app.include_router(budget.router, prefix="/api/v1")
app.include_router(bot.router, prefix="/api/v1")
app.include_router(recurring.router, prefix="/api/v1")
app.include_router(analytics.router, prefix="/api/v1")
app.include_router(events.router, prefix="/api/v1")
app.include_router(goals.router, prefix="/api/v1")
app.include_router(notifications.router, prefix="/api/v1")
app.include_router(income.router, prefix="/api/v1")
app.include_router(receipts.router, prefix="/api/v1")
app.include_router(bank_import.router, prefix="/api/v1")
app.include_router(currency.router, prefix="/api/v1")
app.include_router(social.router, prefix="/api/v1")
app.include_router(cards.router, prefix="/api/v1")
app.include_router(group_goals.router, prefix="/api/v1")

@app.on_event("startup")
def seed_categories():
    db = SessionLocal()
    defaults = ["Еда", "Транспорт", "Жильё", "Развлечения", "Здоровье", "Прочее"]
    existing = db.query(models.Category).filter(models.Category.is_default == 1).count()
    if existing == 0:
        for name in defaults:
            db.add(models.Category(name=name, is_default=1, user_id=None))
        db.commit()
    db.close()

@app.on_event("startup")
def seed_events():
    from datetime import date
    db = SessionLocal()
    existing = db.query(models.Event).count()
    if existing == 0:
        events = [
            models.Event(country="RU", name="Новый год", event_date=date(2026, 1, 1), warning_message="Скоро Новый год — обычно траты заметно выше."),
            models.Event(country="RU", name="Начало зимней сессии", event_date=date(2026, 1, 15), warning_message="Экзаменационный период — учтите расходы на подготовку."),
            models.Event(country="RU", name="Стипендия", event_date=date(2026, 1, 25), warning_message="Обычно приходит стипендия в эти дни."),
            models.Event(country="RU", name="Начало летней сессии", event_date=date(2026, 6, 1), warning_message="Экзаменационный период — учтите расходы на подготовку."),
            models.Event(country="IN", name="Diwali", event_date=date(2026, 11, 1), warning_message="Скоро Diwali — обычно траты заметно выше."),
            models.Event(country="IN", name="Начало сессии", event_date=date(2026, 12, 1), warning_message="Экзаменационный период — учтите расходы на подготовку."),
            models.Event(country="IN", name="Holi", event_date=date(2026, 3, 1), warning_message="Скоро Holi — обычно траты заметно выше."),
        ]
        db.add_all(events)
        db.commit()
    db.close()


@app.on_event("startup")
def seed_exchange_rates():
    db = SessionLocal()
    existing = db.query(models.ExchangeRate).count()
    if existing == 0:
        # курсы примерные, для реального использования обновляются через /currencies/rates
        db.add(models.ExchangeRate(currency_code="RUB", rate_to_rub=1))
        db.add(models.ExchangeRate(currency_code="INR", rate_to_rub=1.1))  # 1 INR ≈ 1.1 RUB, ориентировочно
        db.add(models.ExchangeRate(currency_code="USD", rate_to_rub=95))
        db.commit()
    db.close()


@app.get("/")
def root():
    return {"status": "Cash Compass backend is alive"}