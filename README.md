# Cash Compass — Backend

Бэкенд для приложения по управлению личным бюджетом для студентов (Россия/Индия).

**Публичный сервер:** `https://web-production-f4c9c.up.railway.app`
**Документация API:** `https://web-production-f4c9c.up.railway.app/docs`

## Стек

- **Язык**: Python 3.12
- **Фреймворк**: FastAPI
- **База данных**: MySQL
- **ORM**: SQLAlchemy
- **Авторизация**: JWT (python-jose) + хеширование паролей (passlib/bcrypt)
- **ИИ**: Claude API (Anthropic) — генерация комментариев бота, распознавание чеков (Vision)
- **Хостинг**: Railway (веб-сервис + управляемая MySQL)

## Функционал

### Основа
- Регистрация и авторизация (JWT), профиль с указанием страны, уровня образования, вуза
- CRUD транзакций (доходы/расходы), категории (системные + пользовательские)
- Месячный и недельный бюджет с автоматическим прогресс-баром
- Регулярные расходы/подписки, обнаружение повторяющихся/забытых подписок

### Аналитика и прогнозы
- Агрегация расходов по категориям, дням, сравнение месяц-к-месяцу
- Прогноз траты бюджета ("закончится через N дней")
- Обнаружение аномалий в доходах (задержка, падение суммы)

### Цели и накопления
- Личные цели/копилки с milestone-уведомлениями (25/50/75/100%)
- Прогноз достижения цели по текущему темпу
- Групповые накопления с приглашением по коду

### ИИ-функции
- Бот-ассистент: шаблонные советы по бюджету + fallback-генерация через Claude API
- Сканирование чеков через камеру (Claude Vision) с подтверждением перед созданием транзакций
- Импорт банковских выписок (CSV/PDF) с авто-категоризацией

### Дополнительно
- Спонтанные расходы с тегами причины (эмоция/компания/скидка/импульс)
- Статичный календарь событий по странам (сессии, праздники, стипендии)
- Базовая мультивалютность (RUB как опорная валюта)
- Анонимизированное социальное сравнение между вузами (с защитой при малой выборке)
- Карточки финансовой грамотности, показываются по релевантности к поведению пользователя
- Массовая рассылка советов бота всем пользователям (защищённый админ-эндпоинт)

## Установка и запуск (локально)

### 1. Требования

- Python 3.12
- MySQL (например, через XAMPP)
- Виртуальное окружение (venv)

### 2. Клонирование и окружение

```bash
git clone https://github.com/GlebAssick/Cash-Compass-Backend.git
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
ADMIN_TRIGGER_KEY=секретный_ключ_для_админ_эндпоинтов
```

Если `ANTHROPIC_API_KEY` не указан — бот и сканирование чеков работают в режиме честного fallback, приложение не падает.

### 5. Создание базы данных

Создайте базу `cash_compass` с кодировкой `utf8mb4_general_ci`. Основные таблицы создаются автоматически при первом запуске. Если база уже существовала до добавления полей мультивалютности/вуза, потребуются миграции (см. `MIGRATIONS.md`, если ведёте отдельный файл, либо ниже).

**Ручные миграции** (нужны только при обновлении уже существующей БД, не при создании с нуля):
```sql
ALTER TABLE transactions ADD COLUMN is_spontaneous INT DEFAULT 0;
ALTER TABLE transactions ADD COLUMN tag ENUM('emotional','company','discount','impulse') NULL;
ALTER TABLE transactions ADD COLUMN income_source_id INT NULL;
ALTER TABLE transactions ADD COLUMN currency VARCHAR(3) NOT NULL DEFAULT 'RUB';
ALTER TABLE users ADD COLUMN base_currency VARCHAR(3) NOT NULL DEFAULT 'RUB';
ALTER TABLE users ADD COLUMN university VARCHAR(150) NULL;
```

### 6. Запуск

```bash
uvicorn app.main:app --reload
```

Сервер поднимется на `http://127.0.0.1:8000`, документация на `/docs`.

## Деплой

Проект развёрнут на Railway. Процесс:
1. Push в `main` ветку GitHub-репозитория
2. Railway автоматически пересобирает и деплоит `web`-сервис
3. Переменные окружения настраиваются в Railway → Variables (аналогично `.env`)
4. `DATABASE_URL` использует ссылку на переменные сервиса MySQL: `mysql+pymysql://${{MySQL.MYSQLUSER}}:${{MySQL.MYSQLPASSWORD}}@${{MySQL.MYSQLHOST}}:${{MySQL.MYSQLPORT}}/${{MySQL.MYSQLDATABASE}}`

## Структура проекта

```
cash-compass-backend/
├── app/
│   ├── main.py                 # точка входа, роутеры, CORS, seed-функции
│   ├── database.py             # подключение к БД
│   ├── models.py                # все таблицы (SQLAlchemy)
│   ├── schemas.py                # схемы валидации (Pydantic)
│   ├── auth.py                    # JWT, хеширование, проверка пользователя
│   ├── bot_phrases.py             # шаблоны ответов бота
│   ├── claude_bot.py              # интеграция с Claude API + fallback (комментарии, распознавание чеков)
│   ├── bank_parser.py             # парсинг CSV/PDF банковских выписок
│   ├── currency_utils.py          # конвертация валют
│   ├── financial_cards.py         # условия и тексты карточек финграмотности
│   └── routers/
│       ├── auth.py                # /auth
│       ├── categories.py          # /categories
│       ├── transactions.py        # /transactions
│       ├── budget.py               # /budget (месячный, недельный, прогноз)
│       ├── bot.py                  # /bot (комментарий, рассылка)
│       ├── recurring.py            # /recurring (подписки, waste-detection)
│       ├── analytics.py            # /analytics (графики, сравнение месяцев)
│       ├── events.py                # /events (календарь)
│       ├── goals.py                 # /goals (цели, прогноз)
│       ├── notifications.py         # /notifications
│       ├── income.py                # /income (источники, аномалии)
│       ├── receipts.py              # /receipts (сканирование чеков)
│       ├── bank_import.py           # /bank-import (CSV/PDF)
│       ├── currency.py              # /currencies (курсы, конвертация)
│       ├── social.py                # /social (сравнение между вузами)
│       ├── cards.py                 # /cards (финансовая грамотность)
│       └── group_goals.py           # /group-goals (групповые накопления)
├── tests/
│   └── test_main.py             # 34 теста, покрывают весь функционал
├── conftest.py                    # настройка путей для pytest
├── Procfile                        # команда запуска для Railway
├── requirements.txt
├── .env                              # переменные окружения (не в git)
└── .gitignore
```

## Основные эндпоинты

Базовый путь: `/api/v1`

| Раздел | Примеры путей |
|---|---|
| Авторизация | `POST /auth/register`, `POST /auth/login` |
| Категории | `GET,POST /categories/` |
| Транзакции | `GET,POST /transactions/`, `PUT,DELETE /transactions/{id}` |
| Бюджет | `GET,POST /budget/`, `POST /budget/weekly`, `GET /budget/forecast` |
| Бот | `GET /bot/comment`, `POST /bot/broadcast-comments` (admin) |
| Подписки | `GET,POST /recurring/`, `DELETE /recurring/{id}`, `GET /recurring/waste-detection` |
| Аналитика | `GET /analytics/by-category`, `/daily`, `/summary`, `/month-comparison` |
| События | `GET /events/all`, `/events/upcoming` |
| Цели | `GET,POST /goals/`, `POST /goals/{id}/contribute`, `GET /goals/{id}/forecast` |
| Уведомления | `GET /notifications/`, `PUT /notifications/{id}/read` |
| Доходы | `GET,POST /income/sources`, `GET /income/anomalies` |
| Чеки | `POST /receipts/scan`, `POST /receipts/confirm` |
| Банк. выписки | `POST /bank-import/csv`, `/pdf`, `POST /bank-import/confirm` |
| Валюты | `GET /currencies/rates`, `POST /currencies/rates` (admin), `GET /currencies/convert` |
| Соц. сравнение | `GET /social/compare` |
| Карточки | `GET /cards/relevant` |
| Групповые цели | `GET,POST /group-goals/`, `POST /group-goals/join`, `POST /group-goals/{id}/contribute` |

Полный интерактивный список — в `/docs`. Все защищённые эндпоинты требуют заголовок `Authorization: Bearer <token>`.

## Тесты

```bash
pytest -v
```

34 теста, покрывают: авторизацию, IDOR-защиту (изоляцию данных между пользователями), полные пользовательские сценарии по каждому модулю.

## Известные ограничения

- PDF-парсер банковских выписок настроен под общий формат "дата-описание-сумма", разные банки могут потребовать адаптации регулярного выражения под конкретный формат
- Конвертация валют реализована в ключевых расчётах (бюджет, соц. сравнение), но не протянута во все агрегации (например, графики в `analytics.py` пока считают без конвертации)
- Функция рассылки бота (`/bot/broadcast-comments`) вызывается вручную или потребует внешнего планировщика (cron) для регулярного автозапуска — сама логика уже реализована
- `CORS` временно открыт для всех источников (`allow_origins=["*"]`) на этапе интеграции с фронтендом, для финального релиза стоит сузить до конкретных доменов