import logging
import secrets
from datetime import datetime, timedelta

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas, auth, email_service
from ..database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

RESET_TOKEN_TTL_MINUTES = 30
VERIFICATION_CODE_TTL_MINUTES = 30
# Дефолтная страна для OAuth-юзеров, у которых её не передали (google всегда
# None, старый yandex-клиент без country). Колонка country NOT NULL, поэтому
# без дефолта создание юзера роняло бэк в 500 (IntegrityError 1048).
DEFAULT_OAUTH_COUNTRY = "RU"


@router.get("/me", response_model=schemas.UserOut)
def get_me(current_user: models.User = Depends(auth.get_current_user)):
    return current_user


@router.post("/register", response_model=schemas.Token)
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.email == user.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email уже зарегистрирован")
    code = f"{secrets.randbelow(1000000):06d}"
    new_user = models.User(
        name=user.name,
        email=user.email,
        hashed_password=auth.hash_password(user.password),
        country=user.country,
        education_level=user.education_level,
        university=user.university,
        verification_code=code,
        verification_code_expires=datetime.utcnow() + timedelta(minutes=VERIFICATION_CODE_TTL_MINUTES),
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    # Честная обработка: юзер уже создан и залогинен токеном, поэтому при сбое
    # Mailgun НЕ откатываем аккаунт и НЕ кидаем 500 (иначе регистрация упадёт
    # из-за почты, хотя профиль живой). Логируем серверно; у юзера есть
    # /auth/resend-verification как fallback, чтобы запросить код повторно.
    sent = email_service.send_verification_email(new_user.email, code)
    if not sent:
        logger.warning(
            "[auth.register] verification email not delivered for %s — "
            "account created, user can request a new code via resend",
            new_user.email,
        )
    token = auth.create_access_token({"sub": str(new_user.id)})
    return {"access_token": token}


@router.post("/verify-email", response_model=schemas.MessageResponse)
def verify_email(payload: schemas.VerifyEmailRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == payload.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    if user.is_verified:
        return {"message": "Email уже подтверждён"}
    if not user.verification_code or user.verification_code != payload.code:
        raise HTTPException(status_code=400, detail="Неверный код подтверждения")
    if user.verification_code_expires and user.verification_code_expires < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Код подтверждения истёк")
    user.is_verified = 1
    user.verification_code = None
    user.verification_code_expires = None
    db.commit()
    return {"message": "Email подтверждён"}


@router.post("/resend-verification", response_model=schemas.MessageResponse)
def resend_verification(payload: schemas.ResendVerificationRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == payload.email).first()
    if user and not user.is_verified:
        code = f"{secrets.randbelow(1000000):06d}"
        user.verification_code = code
        user.verification_code_expires = datetime.utcnow() + timedelta(minutes=VERIFICATION_CODE_TTL_MINUTES)
        db.commit()
        sent = email_service.send_verification_email(user.email, code)
        if not sent:
            # Логируем серверно. Клиенту всё равно отдаём generic-ответ ниже,
            # чтобы эндпоинт нельзя было использовать для перебора email.
            logger.error("[auth.resend] verification email not delivered for %s", user.email)
    # Same response whether or not the account exists, so this endpoint can't be used to probe emails
    return {"message": "Если аккаунт существует, код отправлен повторно"}


@router.post("/forgot-password", response_model=schemas.MessageResponse)
def forgot_password(payload: schemas.ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == payload.email).first()
    if user:
        token = secrets.token_urlsafe(32)
        user.reset_token = token
        user.reset_token_expires = datetime.utcnow() + timedelta(minutes=RESET_TOKEN_TTL_MINUTES)
        db.commit()
        sent = email_service.send_password_reset_email(user.email, token)
        if not sent:
            # Серверно честно фиксируем сбой; клиенту — generic, без утечки
            # существования аккаунта (anti-enumeration).
            logger.error("[auth.forgot] reset email not delivered for %s", user.email)
    # Same response whether or not the account exists, so this endpoint can't be used to probe emails
    return {"message": "Если аккаунт существует, письмо со ссылкой отправлено"}


@router.post("/reset-password", response_model=schemas.MessageResponse)
def reset_password(payload: schemas.ResetPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.reset_token == payload.token).first()
    if not user or not user.reset_token_expires or user.reset_token_expires < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Ссылка недействительна или истекла")
    user.hashed_password = auth.hash_password(payload.new_password)
    user.reset_token = None
    user.reset_token_expires = None
    db.commit()
    return {"message": "Пароль обновлён"}


@router.post("/login", response_model=schemas.Token)
def login(credentials: schemas.UserLogin, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == credentials.email).first()
    if not user or not auth.verify_password(credentials.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Неверный email или пароль")
    token = auth.create_access_token({"sub": str(user.id)})
    return {"access_token": token}


def _issue_token_for_email(db: Session, email: str, name: str | None, country: str | None) -> str:
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        user = models.User(
            name=name or email.split("@")[0],
            email=email,
            hashed_password=None,
            # Дефолт вместо None: колонка country NOT NULL, None ронял 500.
            country=country or DEFAULT_OAUTH_COUNTRY,
            is_verified=1,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info(
            "[auth.oauth] created user id=%s email=%s country=%s",
            user.id, user.email, user.country,
        )
    return auth.create_access_token({"sub": str(user.id)})


@router.post("/oauth/google", response_model=schemas.Token)
def oauth_google(payload: schemas.GoogleOAuthRequest, db: Session = Depends(get_db)):
    resp = httpx.get(
        "https://oauth2.googleapis.com/tokeninfo",
        params={"id_token": payload.id_token},
        timeout=10,
    )
    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid Google token")
    data = resp.json()
    email = data.get("email")
    if not email:
        raise HTTPException(status_code=401, detail="Google token missing email")
    # country=None намеренно: google не отдаёт страну, дефолт RU подставит
    # _issue_token_for_email. Раньше это падало в 500 на NOT NULL.
    token = _issue_token_for_email(db, email, data.get("name"), None)
    return {"access_token": token}


@router.post("/oauth/yandex", response_model=schemas.Token)
def oauth_yandex(payload: schemas.YandexOAuthRequest, db: Session = Depends(get_db)):
    resp = httpx.get(
        "https://login.yandex.ru/info",
        headers={"Authorization": f"OAuth {payload.access_token}"},
        timeout=10,
    )
    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid Yandex token")
    data = resp.json()
    email = data.get("default_email") or (data.get("emails") or [None])[0]
    if not email:
        raise HTTPException(status_code=401, detail="Yandex account has no accessible email")
    name = data.get("real_name") or data.get("display_name")
    # payload.country может прийти None от старого клиента — дефолт спасёт.
    token = _issue_token_for_email(db, email, name, payload.country)
    return {"access_token": token}