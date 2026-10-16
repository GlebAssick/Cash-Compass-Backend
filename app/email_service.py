import os
import json
import urllib.request
import urllib.error

RESEND_API_KEY = os.getenv("RESEND_API_KEY") or os.getenv("SMTP_PASSWORD")
EMAIL_FROM = os.getenv("EMAIL_FROM", "onboarding@resend.dev")
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://cash-compass-gleb.vercel.app")

RESEND_API_URL = "https://api.resend.com/emails"
EMAIL_ENABLED = bool(RESEND_API_KEY)


def _send(to_email: str, subject: str, body: str) -> bool:
    """Send email via Resend REST API (HTTPS port 443 — not blocked by Railway)."""
    if not EMAIL_ENABLED:
        print(f"[email_service] Resend API key not configured, skipping send to {to_email}: {subject}")
        return False

    headers = {
        "Authorization": f"Bearer {RESEND_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "from": EMAIL_FROM,
        "to": [to_email],
        "subject": subject,
        "text": body,
    }

    try:
        req = urllib.request.Request(
            RESEND_API_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=15) as response:
            print(f"[email_service] Email sent successfully to {to_email}: {subject}")
            return True
    except urllib.error.HTTPError as e:
        print(f"[email_service] Resend API HTTP error for {to_email}: {e.code} {e.read().decode('utf-8')}")
        return False
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