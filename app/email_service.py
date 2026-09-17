import os
import smtplib
import ssl
from email.message import EmailMessage

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
EMAIL_FROM = os.getenv("EMAIL_FROM", SMTP_USER or "no-reply@cash-compass.app")
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://cash-compass-ivory.vercel.app")

EMAIL_ENABLED = bool(SMTP_HOST and SMTP_USER and SMTP_PASSWORD)


def _send(to_email: str, subject: str, body: str) -> bool:
    """Send a plain-text email. Returns False (and logs) instead of raising
    if SMTP isn't configured yet, so callers can degrade gracefully."""
    if not EMAIL_ENABLED:
        print(f"[email_service] SMTP not configured, skipping send to {to_email}: {subject}")
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = EMAIL_FROM
    msg["To"] = to_email
    msg.set_content(body)

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls(context=context)
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as exc:
        print(f"[email_service] Failed to send email to {to_email}: {exc}")
        return False


def send_verification_email(to_email: str, code: str) -> bool:
    subject = "Cash Compass — confirm your email"
    body = (
        f"Your Cash Compass verification code is: {code}\n\n"
        f"Enter it on the sign up screen to activate your account.\n"
        f"This code expires in 30 minutes."
    )
    return _send(to_email, subject, body)


def send_password_reset_email(to_email: str, token: str) -> bool:
    reset_link = f"{FRONTEND_URL}/reset-password?token={token}"
    subject = "Cash Compass — reset your password"
    body = (
        f"We received a request to reset your Cash Compass password.\n\n"
        f"Reset it here: {reset_link}\n\n"
        f"This link expires in 30 minutes. If you didn't request this, ignore this email."
    )
    return _send(to_email, subject, body)
