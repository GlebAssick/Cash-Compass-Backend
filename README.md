# Cash Compass — Backend

Бэкенд для приложения по управлению личным бюджетом для студентов (Россия/Индия).

## Стек

- **Язык**: Python 3.12
- **Фреймворк**: FastAPI
- **База данных**: MySQL (через XAMPP для локальной разработки)
- **ORM**: SQLAlchemy
- **Авторизация**: JWT (python-jose) + хеширование паролей (passlib/bcrypt)
- **ИИ-бот**: Claude API (Anthropic) с fallback на шаблонные ответы

## Функционал

- Регистрация и авторизация пользователей (с указанием страны и уровня образования)
- CRUD для транзакций (доходы/расходы)
- Категории расходов (системные + пользовательские)
- Месячный бюджет с автоматическим расчётом остатка и процента использования
- Бот-ассистент, дающий комментарии по бюджету (шаблоны + опциональная генерация через Claude API)

## Установка и запуск

### 1. Требования

- Python 3.12
- XAMPP (модуль MySQL запущен)
- Виртуальное окружение (venv)

### 2. Клонирование и окружение

```bash
git clone <ссылка на репозиторий>
cd cash-compass-backend
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux
```

### 3. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 4. Настройка окружения

Создайте файл `.env` в корне проекта:

```
DATABASE_URL=mysql+pymysql://root:@localhost:3306/cash_compass
SECRET_KEY=ваш_секретный_ключ
ANTHROPIC_API_KEY=ваш_ключ_claude_api_опционально
```

Если `ANTHROPIC_API_KEY` не указан — бот работает в режиме шаблонов с fallback-сообщением вместо живой генерации, приложение не падает.

### 5. Создание базы данных

В phpMyAdmin (`localhost/phpmyadmin`) создайте базу `cash_compass` с кодировкой `utf8mb4_general_ci`. Таблицы создаются автоматически при первом запуске сервера.

### 6. Запуск

```bash
uvicorn app.main:app --reload
```

Сервер поднимется на `http://127.0.0.1:8000`

## API-документация

После запуска сервера полная интерактивная документация доступна по адресу:

```
http://127.0.0.1:8000/docs
```

Там же можно тестировать все эндпоинты через кнопку **Authorize** (нужен `access_token`, полученный через `/auth/login`).

## Структура проекта

```
cash-compass-backend/
├── app/
│   ├── main.py              # точка входа, подключение роутеров
│   ├── database.py          # подключение к БД
│   ├── models.py            # таблицы (SQLAlchemy)
│   ├── schemas.py           # схемы валидации (Pydantic)
│   ├── auth.py               # JWT, хеширование, проверка текущего пользователя
│   ├── bot_phrases.py        # шаблоны ответов бота
│   ├── claude_bot.py         # интеграция с Claude API + fallback
│   └── routers/
│       ├── auth.py           # /auth/register, /auth/login
│       ├── categories.py     # /categories/
│       ├── transactions.py   # /transactions/
│       ├── budget.py         # /budget/
│       └── bot.py            # /bot/comment
├── tests/
│   └── test_main.py          # автотесты (pytest)
├── conftest.py                # настройка путей для pytest
├── requirements.txt
├── .env                        # переменные окружения (не в git)
└── .gitignore
```

## Основные эндпоинты

| Метод | Путь | Описание | Авторизация |
|-------|------|----------|-------------|
| POST | `/auth/register` | Регистрация | Нет |
| POST | `/auth/login` | Вход | Нет |
| GET | `/categories/` | Список категорий | Да |
| POST | `/categories/` | Создать категорию | Да |
| GET | `/transactions/` | Список транзакций | Да |
| POST | `/transactions/` | Создать транзакцию | Да |
| PUT | `/transactions/{id}` | Изменить транзакцию | Да |
| DELETE | `/transactions/{id}` | Удалить транзакцию | Да |
| GET | `/budget/` | Текущий бюджет | Да |
| POST | `/budget/` | Задать месячный бюджет | Да |
| GET | `/bot/comment` | Комментарий бота по бюджету | Да |

Все защищённые эндпоинты требуют заголовок `Authorization: Bearer <token>`.

## Тесты

```bash
pytest -v
```

## Известные ограничения

- Интеграция с Claude API работает в режиме fallback, пока не будет добавлен рабочий `ANTHROPIC_API_KEY` в `.env`
- Функция рассылки советов всем пользователям (не только по запросу) в разработке