import secrets
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .. import models, schemas, auth, email_service
from ..database import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=schemas.UserOut)
def get_me(current_user: models.User = Depends(auth.get_current_user)):
    return current_user

RESET_TOKEN_TTL_MINUTES = 30
VERIFICATION_CODE_TTL_MINUTES = 30


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

    email_service.send_verification_email(new_user.email, code)

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
        email_service.send_verification_email(user.email, code)
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
        email_service.send_password_reset_email(user.email, token)
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