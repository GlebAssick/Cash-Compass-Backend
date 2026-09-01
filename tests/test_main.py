from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "Cash Compass backend is alive"

def test_register_and_login():
    # используем случайный email, чтобы тест можно было гонять много раз подряд
    import random
    email = f"pytest_user_{random.randint(1000,9999)}@test.com"

    register_response = client.post("/api/v1/auth/register", json={
        "email": email,
        "password": "testpass123",
        "country": "RU",
        "education_level": "bachelor_1"
    })
    assert register_response.status_code == 200
    assert "access_token" in register_response.json()

    login_response = client.post("/api/v1/auth/login", json={
        "email": email,
        "password": "testpass123"
    })
    assert login_response.status_code == 200
    assert "access_token" in login_response.json()

def test_login_wrong_password():
    response = client.post("/api/v1/auth/login", json={
        "email": "test@test.com",
        "password": "неверный_пароль"
    })
    assert response.status_code == 401

def test_categories_require_auth():
    # без токена доступ должен быть запрещён
    response = client.get("/api/v1/categories/")
    assert response.status_code in (401, 403)

def test_full_flow():
    import random
    email = f"pytest_flow_{random.randint(1000,9999)}@test.com"

    # регистрация
    register_response = client.post("/api/v1/auth/register", json={
        "email": email,
        "password": "testpass123",
        "country": "RU",
        "education_level": "master"
    })
    token = register_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # получаем категории
    categories_response = client.get("/api/v1/categories/", headers=headers)
    assert categories_response.status_code == 200
    categories = categories_response.json()
    assert len(categories) >= 6  # дефолтные категории

    food_category_id = categories[0]["id"]

    # создаём транзакцию
    tx_response = client.post("/api/v1/transactions/", json={
        "category_id": food_category_id,
        "amount": 750,
        "type": "expense",
        "description": "pytest transaction"
    }, headers=headers)
    assert tx_response.status_code == 200

    # ставим бюджет
    budget_response = client.post("/api/v1/budget/", json={
        "monthly_amount": 20000
    }, headers=headers)
    assert budget_response.status_code == 200
    budget_data = budget_response.json()
    assert float(budget_data["spent"]) == 750.0

    # проверяем, что бот отвечает
    bot_response = client.get("/api/v1/bot/comment", headers=headers)
    assert bot_response.status_code == 200
    assert "comment" in bot_response.json()