import os
import base64
import urllib.request
import urllib.error

MAILGUN_API_KEY = os.getenv("MAILGUN_API_KEY", "")
MAILGUN_DOMAIN = os.getenv("MAILGUN_DOMAIN", "")
EMAIL_FROM = os.getenv("EMAIL_FROM", "noreply@cashcompass.test")
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://cash-compass-gleb.vercel.app")

EMAIL_ENABLED = bool(MAILGUN_API_KEY and MAILGUN_DOMAIN)


def _send(to_email: str, subject: str, body: str) -> bool:
    """Send email via Mailgun HTTPS API (port 443 — not blocked by Railway)."""
    if not EMAIL_ENABLED:
        print(f"[email_service] Mailgun not configured, skipping send to {to_email}: {subject}")
        return False

    url = f"https://api.mailgun.net/v3/{MAILGUN_DOMAIN}/messages"
    credentials = base64.b64encode(f"api:{MAILGUN_API_KEY}".encode()).decode()

    boundary = "----CashCompassBoundary7MA4YWxkTrZu0gW"
    fields = [
        ("from", f"Cash Compass <{EMAIL_FROM}>"),
        ("to", to_email),
        ("subject", subject),
        ("text", body),
    ]

    parts = []
    for name, value in fields:
        parts.append(f"--{boundary}".encode())
        parts.append(f'Content-Disposition: form-data; name="{name}"'.encode())
        parts.append(b"")
        parts.append(value.encode("utf-8"))
    parts.append(f"--{boundary}--".encode())
    parts.append(b"")
    payload = b"\r\n".join(parts)

    headers = {
        "Authorization": f"Basic {credentials}",
        "Content-Type": f"multipart/form-data; boundary={boundary}",
    }

    try:
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=15) as response:
            print(f"[email_service] Email sent successfully to {to_email}: {subject}")
            return True
    except urllib.error.HTTPError as e:
        print(f"[email_service] Mailgun API HTTP error for {to_email}: {e.code} {e.read().decode('utf-8')}")
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