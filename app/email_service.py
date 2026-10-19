import base64
import logging
import os
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)

MAILGUN_API_KEY = os.getenv("MAILGUN_API_KEY", "")
MAILGUN_DOMAIN = os.getenv("MAILGUN_DOMAIN", "")
EMAIL_FROM = os.getenv("EMAIL_FROM", "noreply@cashcompass.test")
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://cash-compass-gleb.vercel.app")
EMAIL_ENABLED = bool(MAILGUN_API_KEY and MAILGUN_DOMAIN)


def _html_wrap(content_html: str) -> str:
    return (
        '<div style="font-family:Arial,Helvetica,sans-serif;background:#f4f5f7;padding:24px;">'
        '<div style="max-width:560px;margin:0 auto;background:#ffffff;border-radius:12px;padding:32px;">'
        '<div style="font-size:20px;font-weight:700;color:#111827;margin-bottom:16px;">Cash Compass</div>'
        + content_html +
        '<div style="margin-top:24px;font-size:12px;color:#6b7280;">'
        "Link expires in 30 minutes. If you didn't request this, ignore this email. "
        "</div></div></div>"
    )


def _send(to_email: str, subject: str, body: str, html: str | None = None) -> bool:
    """Send email via Mailgun HTTPS API (port 443 — not blocked by Railway)."""
    if not EMAIL_ENABLED:
        logger.warning(
            "[email_service] Mailgun not configured, skipping send to %s: %s",
            to_email, subject,
        )
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
    if html:
        fields.append(("html", html))

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
            logger.info("[email_service] Email sent successfully to %s: %s", to_email, subject)
            return True
    except urllib.error.HTTPError as e:
        # Честно логируем код и тело ответа Mailgun, а не молчим.
        try:
            detail = e.read().decode("utf-8", errors="replace")
        except Exception:
            detail = "<unreadable>"
        logger.error(
            "[email_service] Mailgun API HTTP error for %s: %s %s",
            to_email, e.code, detail,
        )
        return False
    except Exception as exc:
        logger.error("[email_service] Failed to send email to %s: %s", to_email, exc)
        return False


def send_verification_email(to_email: str, code: str) -> bool:
    subject = "Cash Compass — confirm your email"
    body = (
        f"Your Cash Compass verification code is: {code}\n\n"
        f"Enter it on the sign up screen to activate your account.\n"
        f"This code expires in 30 minutes. "
    )
    html = _html_wrap(
        '<p style="color:#374151;font-size:14px;">Your verification code:</p>'
        f'<div style="font-size:28px;font-weight:700;letter-spacing:4px;color:#111827;margin:12px 0;">{code}</div>'
        '<p style="color:#6b7280;font-size:12px;">Enter it on the sign up screen. The code expires in 30 minutes.</p>'
    )
    return _send(to_email, subject, body, html)


def send_password_reset_email(to_email: str, token: str) -> bool:
    reset_link = f"{FRONTEND_URL}/reset-password?token={token}"
    subject = "Cash Compass — reset your password"
    body = (
        f"We received a request to reset your Cash Compass password.\n\n"
        f"Reset it here: {reset_link}\n\n"
        f"This link expires in 30 minutes. If you didn't request this, ignore this email. "
    )
    html = _html_wrap(
        '<p style="color:#374151;font-size:14px;">We received a request to reset your Cash Compass password.</p>'
        f'<a href="{reset_link}" style="display:inline-block;background:#111827;color:#ffffff;text-decoration:none;padding:12px 28px;border-radius:8px;font-size:14px;font-weight:600;margin:16px 0;">Reset password</a>'
        f'<p style="color:#6b7280;font-size:12px;">Or copy the link:<br>{reset_link}</p>'
    )
    return _send(to_email, subject, body, html)