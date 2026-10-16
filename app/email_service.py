import os
import smtplib
from email.mime.text import MIMEText

SMTP_HOST = os.getenv("SMTP_HOST", "sandbox.smtp.mailtrap.io")
SMTP_PORT = int(os.getenv("SMTP_PORT", "2525"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
EMAIL_FROM = os.getenv("EMAIL_FROM", "noreply@cashcompass.test")
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://cash-compass-gleb.vercel.app")

EMAIL_ENABLED = bool(SMTP_USER and SMTP_PASSWORD)


def _send(to_email: str, subject: str, body: str) -> bool:
    """Send email via Mailtrap sandbox SMTP (port 2525 — not blocked by Railway)."""
    if not EMAIL_ENABLED:
        print(f"[email_service] SMTP not configured, skipping send to {to_email}: {subject}")
        return False

    msg = MIMEText(body, "plain", "utf-8")
    msg["From"] = f"Cash Compass <{EMAIL_FROM}>"
    msg["To"] = to_email
    msg["Subject"] = subject

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(EMAIL_FROM, [to_email], msg.as_string())
        print(f"[email_service] Email sent successfully to {to_email}: {subject}")
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