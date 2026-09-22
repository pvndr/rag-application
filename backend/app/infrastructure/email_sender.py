import json
import logging
import re
import ssl
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

# Some portable Python builds ship without a default CA bundle and cannot
# verify api.sendgrid.com's chain. Prefer certifi when present; otherwise
# fall back to the interpreter's default verification paths.
try:
    import certifi

    _SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except ImportError:  # pragma: no cover - certifi ships with most installs
    _SSL_CONTEXT = None


class EmailDeliveryError(Exception):
    pass


@dataclass(frozen=True)
class PasswordResetEmail:
    to_email: str
    reset_url: str


class EmailSender:
    def send_password_reset(self, email: PasswordResetEmail) -> None:
        raise NotImplementedError


class SendGridEmailSender(EmailSender):
    def __init__(self, api_key: str | None, from_email: str, app_name: str) -> None:
        self._api_key = api_key
        self._from_email = from_email
        self._app_name = app_name

    def send_password_reset(self, email: PasswordResetEmail) -> None:
        if not self._api_key:
            raise EmailDeliveryError(
                "Password reset email is not configured. Set SENDGRID_API_KEY in backend/.env."
            )

        from_name, from_address = _split_from_email(self._from_email)
        payload = {
            "personalizations": [{"to": [{"email": email.to_email}]}],
            "from": {"email": from_address, "name": from_name},
            "subject": f"Reset your {self._app_name} password",
            "content": [
                {"type": "text/plain", "value": _password_reset_text(self._app_name, email.reset_url)},
                {"type": "text/html", "value": _password_reset_html(self._app_name, email.reset_url)},
            ],
        }
        request = Request(
            "https://api.sendgrid.com/v3/mail/send",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=10, context=_SSL_CONTEXT) as response:
                if response.status >= 400:
                    raise EmailDeliveryError("SendGrid rejected the password reset email.")
        except HTTPError as exc:
            message = exc.read().decode("utf-8", errors="ignore")
            logger.error("SendGrid returned HTTP %s: %s", exc.code, message)
            raise EmailDeliveryError(f"SendGrid rejected the password reset email. {message}") from exc
        except URLError as exc:
            # exc.reason names the failure category (DNS, TLS, refused) and
            # never contains the Authorization header or API key.
            reason = type(exc.reason).__name__ if exc.reason is not None else type(exc).__name__
            logger.error("SendGrid connection failed (%s): %s", reason, exc.reason)
            raise EmailDeliveryError(
                f"Could not connect to SendGrid to send email. ({reason}: {exc.reason})"
            ) from exc


def _split_from_email(from_email: str) -> tuple[str, str]:
    """Split a 'Name <address>' string into (name, address)."""
    match = re.fullmatch(r"\s*(.*?)\s*<([^>]+)>\s*", from_email)
    if match:
        return match.group(1) or from_email.strip(), match.group(2).strip()
    return from_email.strip(), from_email.strip()


def _password_reset_html(app_name: str, reset_url: str) -> str:
    return f"""
    <div style="font-family: Arial, sans-serif; line-height: 1.6; color: #1c1917;">
      <h2>Reset your {app_name} password</h2>
      <p>We received a request to reset your password.</p>
      <p>
        <a href="{reset_url}" style="display: inline-block; background: #1c1917; color: #ffffff; padding: 10px 14px; text-decoration: none; border-radius: 4px;">
          Reset password
        </a>
      </p>
      <p>This link expires soon and can only be used once.</p>
      <p>If you did not request this, you can safely ignore this email.</p>
    </div>
    """.strip()


def _password_reset_text(app_name: str, reset_url: str) -> str:
    return (
        f"Reset your {app_name} password\n\n"
        "We received a request to reset your password.\n\n"
        f"Open this link to set a new password: {reset_url}\n\n"
        "This link expires soon and can only be used once. "
        "If you did not request this, you can safely ignore this email."
    )
