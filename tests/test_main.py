"""
Тесты Cash Compass Backend.

Структура:
- Core: базовые проверки (health-check, регистрация, авторизация)
- Transactions & Categories: CRUD транзакций, категории
- Budget: месячный/недельный бюджет, прогноз трат
- Bot: комментарии бота (шаблоны/fallback)
- Recurring: регулярные платежи, waste-detection
- Analytics: агрегация данных для графиков
- Events: календарь событий
- Goals: цели/копилки, milestone-уведомления, прогноз
- Notifications: уведомления
- Income: источники дохода
- Currency: конвертация валют
- Social: социальное сравнение
- Cards: карточки финансовой грамотности
- Group Goals: групповые накопления
"""

import random
from decimal import Decimal
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

def register_user(country="RU", education_level="bachelor_1", university=None):
    """Регистрирует нового пользователя со случайным email и возвращает (email, headers)."""
    email = f"pytest_{random.randint(100000, 999999)}@test.com"
    payload = {
        "name": "Pytest User",
        "email": email,
        "password": "testpass123",
        "country": country,
        "education_level": education_level,
    }
    if university:
        payload["university"] = university

    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    return email, headers


def get_food_category_id(headers) -> int:
    """Возвращает id дефолтной категории 'Еда' (или первой доступной, если её нет)."""
    response = client.get("/api/v1/categories/", headers=headers)
    assert response.status_code == 200
    categories = response.json()
    assert len(categories) >= 1
    for c in categories:
        if c["name"] == "Еда":
            return c["id"]
    return categories[0]["id"]


def create_transaction(headers, category_id, amount=500, tx_type="expense", **extra):
    payload = {
        "category_id": category_id,
        "amount": amount,
        "type": tx_type,
        "description": extra.pop("description", "pytest transaction"),
        **extra,
    }
    response = client.post("/api/v1/transactions/", json=payload, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def set_monthly_budget(headers, amount=30000):
    response = client.post("/api/v1/budget/", json={"monthly_amount": amount}, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------

def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "Cash Compass backend is alive"


def test_register_and_login():
    email, _ = register_user()

    login_response = client.post("/api/v1/auth/login", json={
        "email": email,
        "password": "testpass123",
    })
    assert login_response.status_code == 200
    assert "access_token" in login_response.json()


def test_login_wrong_password():
    email, _ = register_user()
    response = client.post("/api/v1/auth/login", json={
        "email": email,
        "password": "неверный_пароль",
    })
    assert response.status_code == 401


def test_categories_require_auth():
    response = client.get("/api/v1/categories/")
    assert response.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Transactions & Categories
# ---------------------------------------------------------------------------

def test_full_transaction_flow():
    _, headers = register_user()
    category_id = get_food_category_id(headers)

    tx = create_transaction(headers, category_id, amount=750)
    assert tx["amount"] == "750.00" or float(tx["amount"]) == 750.0

    list_response = client.get("/api/v1/transactions/", headers=headers)
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1


def test_transaction_delete_requires_ownership():
    _, headers_a = register_user()
    _, headers_b = register_user()
    category_id = get_food_category_id(headers_a)

    tx = create_transaction(headers_a, category_id)

    # пользователь B не должен суметь удалить транзакцию пользователя A
    response = client.delete(f"/api/v1/transactions/{tx['id']}", headers=headers_b)
    assert response.status_code == 404


def test_spontaneous_transaction_with_tag():
    _, headers = register_user()
    category_id = get_food_category_id(headers)

    tx = create_transaction(headers, category_id, is_spontaneous=True, tag="emotional")
    assert tx["is_spontaneous"] == 1
    assert tx["tag"] == "emotional"


# ---------------------------------------------------------------------------
# Budget
# ---------------------------------------------------------------------------

def test_monthly_budget_calculates_spent():
    _, headers = register_user()
    category_id = get_food_category_id(headers)
    create_transaction(headers, category_id, amount=500)

    budget = set_monthly_budget(headers, amount=20000)
    assert float(budget["spent"]) == 500.0
    assert float(budget["remaining"]) == 19500.0


def test_weekly_budget_within_monthly():
    _, headers = register_user()
    set_monthly_budget(headers, amount=30000)

    response = client.post("/api/v1/budget/weekly", json={"week_amount": 5000}, headers=headers)
    assert response.status_code == 200
    assert float(response.json()["week_amount"]) == 5000.0

    current = client.get("/api/v1/budget/weekly/current", headers=headers)
    assert current.status_code == 200


def test_weekly_budget_rejects_overspend():
    _, headers = register_user()
    set_monthly_budget(headers, amount=1000)

    response = client.post("/api/v1/budget/weekly", json={"week_amount": 5000}, headers=headers)
    assert response.status_code == 400


def test_budget_forecast_endpoint():
    _, headers = register_user()
    set_monthly_budget(headers, amount=10000)
    category_id = get_food_category_id(headers)
    create_transaction(headers, category_id, amount=1000)

    response = client.get("/api/v1/budget/forecast", headers=headers)
    assert response.status_code == 200
    assert "status" in response.json()


# ---------------------------------------------------------------------------
# Bot
# ---------------------------------------------------------------------------

def test_bot_comment_without_budget():
    _, headers = register_user()
    response = client.get("/api/v1/bot/comment", headers=headers)
    assert response.status_code == 200
    assert response.json()["source"] == "static"


def test_bot_comment_with_budget_uses_template():
    _, headers = register_user()
    set_monthly_budget(headers, amount=30000)

    response = client.get("/api/v1/bot/comment", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert "comment" in body
    assert body["source"] in ("template", "claude_api")


def test_broadcast_comments_requires_admin_key():
    response = client.post(
        "/api/v1/bot/broadcast-comments",
        headers={"X-Admin-Key": "wrong_key_12345"},
    )
    assert response.status_code == 403

# ---------------------------------------------------------------------------
# Recurring expenses
# ---------------------------------------------------------------------------

def test_recurring_expense_lifecycle():
    _, headers = register_user()
    category_id = get_food_category_id(headers)

    create_response = client.post("/api/v1/recurring/", json={
        "category_id": category_id,
        "name": "Spotify",
        "amount": 300,
        "day_of_month": 5,
    }, headers=headers)
    assert create_response.status_code == 200
    recurring_id = create_response.json()["id"]

    list_response = client.get("/api/v1/recurring/", headers=headers)
    assert any(r["id"] == recurring_id for r in list_response.json())

    delete_response = client.delete(f"/api/v1/recurring/{recurring_id}", headers=headers)
    assert delete_response.status_code == 200

    list_after = client.get("/api/v1/recurring/", headers=headers)
    assert all(r["id"] != recurring_id for r in list_after.json())


def test_waste_detection_returns_structure():
    _, headers = register_user()
    response = client.get("/api/v1/recurring/waste-detection", headers=headers)
    assert response.status_code == 200
    assert "findings" in response.json()


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

def test_analytics_endpoints_return_data():
    _, headers = register_user()
    category_id = get_food_category_id(headers)
    create_transaction(headers, category_id, amount=500)

    for path in ["by-category", "daily", "summary", "month-comparison"]:
        response = client.get(f"/api/v1/analytics/{path}", headers=headers)
        assert response.status_code == 200, f"{path} failed: {response.text}"


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

def test_events_for_country():
    _, headers = register_user(country="RU")
    response = client.get("/api/v1/events/all", headers=headers)
    assert response.status_code == 200
    assert all(e["country"] == "RU" for e in response.json())


def test_upcoming_events_structure():
    _, headers = register_user()
    response = client.get("/api/v1/events/upcoming", headers=headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


# ---------------------------------------------------------------------------
# Goals
# ---------------------------------------------------------------------------

def test_goal_creation_and_progress():
    _, headers = register_user()

    create_response = client.post("/api/v1/goals/", json={
        "name": "Ноутбук",
        "target_amount": 1000,
    }, headers=headers)
    assert create_response.status_code == 200
    goal_id = create_response.json()["id"]
    assert create_response.json()["progress_percent"] == 0.0

    contribute_response = client.post(f"/api/v1/goals/{goal_id}/contribute", json={
        "amount": 250,
    }, headers=headers)
    assert contribute_response.status_code == 200
    assert contribute_response.json()["progress_percent"] == 25.0


def test_goal_milestone_creates_notification():
    _, headers = register_user()

    goal = client.post("/api/v1/goals/", json={"name": "Цель", "target_amount": 1000}, headers=headers).json()
    client.post(f"/api/v1/goals/{goal['id']}/contribute", json={"amount": 500}, headers=headers)

    notifications = client.get("/api/v1/notifications/", headers=headers).json()
    assert any("50%" in n["message"] for n in notifications)


def test_goal_isolated_between_users():
    _, headers_a = register_user()
    _, headers_b = register_user()

    goal = client.post("/api/v1/goals/", json={"name": "Приватная цель", "target_amount": 500}, headers=headers_a).json()

    # пользователь B не должен видеть/пополнять чужую цель
    response = client.post(f"/api/v1/goals/{goal['id']}/contribute", json={"amount": 100}, headers=headers_b)
    assert response.status_code == 404


def test_goal_delete():
    _, headers = register_user()
    goal = client.post("/api/v1/goals/", json={"name": "Временная", "target_amount": 100}, headers=headers).json()

    response = client.delete(f"/api/v1/goals/{goal['id']}", headers=headers)
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

def test_notifications_mark_as_read():
    _, headers = register_user()
    goal = client.post("/api/v1/goals/", json={"name": "Цель", "target_amount": 100}, headers=headers).json()
    client.post(f"/api/v1/goals/{goal['id']}/contribute", json={"amount": 100}, headers=headers)

    notifications = client.get("/api/v1/notifications/", headers=headers).json()
    assert len(notifications) >= 1

    notification_id = notifications[0]["id"]
    response = client.put(f"/api/v1/notifications/{notification_id}/read", headers=headers)
    assert response.status_code == 200


def test_notifications_isolated_between_users():
    _, headers_a = register_user()
    _, headers_b = register_user()
    goal = client.post("/api/v1/goals/", json={"name": "Цель", "target_amount": 100}, headers=headers_a).json()
    client.post(f"/api/v1/goals/{goal['id']}/contribute", json={"amount": 100}, headers=headers_a)

    notifications_a = client.get("/api/v1/notifications/", headers=headers_a).json()
    notification_id = notifications_a[0]["id"]

    # пользователь B не должен суметь отметить чужое уведомление прочитанным
    response = client.put(f"/api/v1/notifications/{notification_id}/read", headers=headers_b)
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Income
# ---------------------------------------------------------------------------

def test_income_source_creation():
    _, headers = register_user()
    response = client.post("/api/v1/income/sources", json={
        "name": "Стипендия",
        "expected_amount": 5000,
        "expected_day_of_month": 25,
    }, headers=headers)
    assert response.status_code == 200

    list_response = client.get("/api/v1/income/sources", headers=headers)
    assert len(list_response.json()) == 1


def test_income_anomalies_structure():
    _, headers = register_user()
    response = client.get("/api/v1/income/anomalies", headers=headers)
    assert response.status_code == 200
    assert "anomalies" in response.json()


# ---------------------------------------------------------------------------
# Currency
# ---------------------------------------------------------------------------

def test_currency_convert_same_currency():
    _, headers = register_user()
    response = client.get("/api/v1/currencies/convert", params={
        "amount": 100, "from": "RUB", "to": "RUB",
    }, headers=headers)
    assert response.status_code == 200
    assert float(response.json()["converted_amount"]) == 100.0

def test_set_rate_requires_admin_key():
    response = client.post(
        "/api/v1/currencies/rates",
        json={"currency_code": "EUR", "rate_to_rub": 100},
        headers={"X-Admin-Key": "wrong_key_12345"},
    )
    assert response.status_code == 403

# ---------------------------------------------------------------------------
# Social comparison
# ---------------------------------------------------------------------------

def test_social_compare_structure():
    _, headers = register_user(university="МГУ")
    response = client.get("/api/v1/social/compare", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert "your_total" in body
    assert "message" in body


# ---------------------------------------------------------------------------
# Financial literacy cards
# ---------------------------------------------------------------------------

def test_relevant_cards_structure():
    _, headers = register_user()
    response = client.get("/api/v1/cards/relevant", headers=headers)
    assert response.status_code == 200
    assert "cards" in response.json()


# ---------------------------------------------------------------------------
# Group goals
# ---------------------------------------------------------------------------

def test_group_goal_creation_and_membership():
    _, headers = register_user()

    create_response = client.post("/api/v1/group-goals/", json={
        "name": "Подарок другу",
        "target_amount": 3000,
    }, headers=headers)
    assert create_response.status_code == 200
    body = create_response.json()
    assert len(body["members"]) == 1
    assert "invite_code" in body


def test_group_goal_join_and_contribute():
    _, headers_a = register_user()
    _, headers_b = register_user()

    goal = client.post("/api/v1/group-goals/", json={"name": "Поездка", "target_amount": 2000}, headers=headers_a).json()

    join_response = client.post("/api/v1/group-goals/join", json={
        "invite_code": goal["invite_code"],
    }, headers=headers_b)
    assert join_response.status_code == 200
    assert len(join_response.json()["members"]) == 2

    contribute_response = client.post(f"/api/v1/group-goals/{goal['id']}/contribute", json={
        "amount": 500,
    }, headers=headers_b)
    assert contribute_response.status_code == 200
    assert float(contribute_response.json()["current_amount"]) == 500.0


def test_group_goal_requires_membership():
    _, headers_a = register_user()
    _, headers_b = register_user()

    goal = client.post("/api/v1/group-goals/", json={"name": "Приватная группа", "target_amount": 1000}, headers=headers_a).json()

    # пользователь B не состоит в группе — доступ должен быть запрещён
    response = client.get(f"/api/v1/group-goals/{goal['id']}", headers=headers_b)
    assert response.status_code == 403