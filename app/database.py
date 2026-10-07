from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv
import os
import certifi

load_dotenv()

SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

# Для облачной MySQL (TiDB/Aiven) нужен SSL; локально (XAMPP) не нужен
connect_args = {}
if os.getenv("DB_SSL", "false").lower() == "true":
    connect_args["ssl"] = {"ca": certifi.where()}

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,   # проверять соединение перед использованием
    pool_recycle=300,     # облачные БД закрывают простаивающие соединения
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()