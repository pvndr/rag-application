import base64
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import bcrypt

from app.core.config import settings
from app.domain.entities import User
from app.infrastructure.email_sender import EmailDeliveryError, EmailSender, PasswordResetEmail
from app.infrastructure.sqlite_store import SqliteTokenRepository, SqliteUserRepository


class AuthError(Exception):
    pass


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = settings.access_token_expire_minutes * 60


class AuthService:
    def __init__(
        self,
        users: SqliteUserRepository,
        tokens: SqliteTokenRepository,
        email_sender: EmailSender,
    ) -> None:
        self._users = users
        self._tokens = tokens
        self._email_sender = email_sender

    def register(self, name: str, email: str, password: str) -> tuple[User, TokenPair]:
        if self._users.get_by_email(email):
            raise AuthError("An account with this email already exists.")
        user = self._users.create(
            name=name.strip(),
            email=email.strip().lower(),
            password_hash=_hash_password(password),
        )
        return user, self._issue_tokens(user)

    def login(self, email: str, password: str) -> tuple[User, TokenPair]:
        user = self._users.get_by_email(email)
        if user is None or not _verify_password(password, user.password_hash):
            raise AuthError("Invalid email or password.")
        return user, self._issue_tokens(user)

    def refresh(self, refresh_token: str) -> TokenPair:
        payload = verify_jwt(refresh_token, expected_type="refresh")
        token_id = str(payload["jti"])
        row = self._tokens.get_refresh_token(token_id)
        if row is None or row["revoked_at"]:
            raise AuthError("Refresh token is invalid.")
        if datetime.fromisoformat(str(row["expires_at"])) <= datetime.now(timezone.utc):
            raise AuthError("Refresh token has expired.")
        if not hmac.compare_digest(str(row["token_hash"]), _hash_token(refresh_token)):
            raise AuthError("Refresh token is invalid.")

        self._tokens.revoke_refresh_token(token_id)
        user = self._users.get(str(payload["sub"]))
        if user is None:
            raise AuthError("User no longer exists.")
        return self._issue_tokens(user)

    def logout(self, refresh_token: str) -> None:
        try:
            payload = verify_jwt(refresh_token, expected_type="refresh")
        except AuthError:
            return
        self._tokens.revoke_refresh_token(str(payload["jti"]))

    def get_user_from_access_token(self, access_token: str) -> User:
        payload = verify_jwt(access_token, expected_type="access")
        user = self._users.get(str(payload["sub"]))
        if user is None:
            raise AuthError("User no longer exists.")
        return user

    def send_password_reset_email(self, email: str) -> None:
        user = self._users.get_by_email(email)
        if user is None:
            return
        raw_token = secrets.token_urlsafe(32)
        token_id = self._tokens.create_password_reset(
            user.id,
            _hash_token(raw_token),
            datetime.now(timezone.utc)
            + timedelta(minutes=settings.password_reset_token_expire_minutes),
        )
        reset_token = f"{token_id}.{raw_token}"
        reset_url = f"{settings.app_base_url.rstrip('/')}/reset-password?token={reset_token}"
        try:
            self._email_sender.send_password_reset(
                PasswordResetEmail(to_email=user.email, reset_url=reset_url)
            )
        except EmailDeliveryError as exc:
            raise AuthError(str(exc)) from exc

    def reset_password(self, reset_token: str, new_password: str) -> None:
        try:
            token_id, raw_token = reset_token.split(".", maxsplit=1)
        except ValueError as exc:
            raise AuthError("Reset token is invalid.") from exc
        row = self._tokens.get_password_reset(token_id)
        if row is None or row["used_at"]:
            raise AuthError("Reset token is invalid.")
        if datetime.fromisoformat(str(row["expires_at"])) <= datetime.now(timezone.utc):
            raise AuthError("Reset token has expired.")
        if not hmac.compare_digest(str(row["token_hash"]), _hash_token(raw_token)):
            raise AuthError("Reset token is invalid.")

        self._users.update_password(str(row["user_id"]), _hash_password(new_password))
        self._tokens.mark_password_reset_used(token_id)

    def _issue_tokens(self, user: User) -> TokenPair:
        refresh_token_id = str(uuid4())
        access_token = create_jwt(
            subject=user.id,
            token_type="access",
            expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
            extra={"role": user.role, "email": user.email},
        )
        refresh_token = create_jwt(
            subject=user.id,
            token_type="refresh",
            expires_delta=timedelta(days=settings.refresh_token_expire_days),
            jti=refresh_token_id,
        )
        self._tokens.save_refresh_token(
            refresh_token_id,
            user.id,
            _hash_token(refresh_token),
            datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days),
        )
        return TokenPair(access_token=access_token, refresh_token=refresh_token)


def create_jwt(
    subject: str,
    token_type: str,
    expires_delta: timedelta,
    extra: dict[str, str] | None = None,
    jti: str | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, object] = {
        "sub": subject,
        "typ": token_type,
        "iss": settings.jwt_issuer,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
        "jti": jti or str(uuid4()),
    }
    payload.update(extra or {})
    header = {"alg": "HS256", "typ": "JWT"}
    signing_input = f"{_b64_json(header)}.{_b64_json(payload)}"
    signature = hmac.new(
        settings.jwt_secret_key.encode("utf-8"),
        signing_input.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return f"{signing_input}.{_b64(signature)}"


def verify_jwt(token: str, expected_type: str) -> dict[str, object]:
    try:
        header_b64, payload_b64, signature_b64 = token.split(".")
        signing_input = f"{header_b64}.{payload_b64}"
        expected_signature = hmac.new(
            settings.jwt_secret_key.encode("utf-8"),
            signing_input.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(_b64(expected_signature), signature_b64):
            raise AuthError("Token signature is invalid.")
        payload = json.loads(_b64_decode(payload_b64))
    except (ValueError, json.JSONDecodeError) as exc:
        raise AuthError("Token is invalid.") from exc

    if payload.get("iss") != settings.jwt_issuer or payload.get("typ") != expected_type:
        raise AuthError("Token is invalid.")
    if int(payload.get("exp", 0)) <= int(datetime.now(timezone.utc).timestamp()):
        raise AuthError("Token has expired.")
    return payload


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _b64_json(payload: dict[str, object]) -> str:
    return _b64(json.dumps(payload, separators=(",", ":")).encode("utf-8"))


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64_decode(value: str) -> str:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}").decode("utf-8")
