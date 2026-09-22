from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken  # type: ignore

from .config import settings


class EncryptionError(Exception):
    """Base error for encryption operations."""
    pass


class EncryptionConfigurationError(EncryptionError):
    """Raised when PROVIDER_ENCRYPTION_KEY is missing or malformed."""
    pass


def _get_fernet(encryption_key: str | None = None) -> Fernet:
    key = encryption_key if encryption_key is not None else settings.provider_encryption_key
    if not key or not str(key).strip():
        raise EncryptionConfigurationError(
            "PROVIDER_ENCRYPTION_KEY is not configured. Set it in backend/.env or environment secrets."
        )
    try:
        return Fernet(key.encode("utf-8") if isinstance(key, str) else key)
    except Exception as exc:
        raise EncryptionConfigurationError("PROVIDER_ENCRYPTION_KEY is invalid.") from exc


def encrypt_api_key(api_key: str, encryption_key: str | None = None) -> str:
    """Encrypts a plaintext API key. Plaintext key is never logged or leaked."""
    if not api_key or not api_key.strip():
        raise EncryptionError("API key cannot be empty.")
    fernet = _get_fernet(encryption_key)
    token = fernet.encrypt(api_key.strip().encode("utf-8"))
    return token.decode("utf-8")


def decrypt_api_key(encrypted_key: str, encryption_key: str | None = None) -> str:
    """Decrypts an encrypted API key. Plaintext key is never logged or leaked."""
    fernet = _get_fernet(encryption_key)
    try:
        decrypted = fernet.decrypt(encrypted_key.encode("utf-8"))
        return decrypted.decode("utf-8")
    except InvalidToken as exc:
        raise EncryptionError("Failed to decrypt API key: invalid or tampered ciphertext.") from exc
    except Exception as exc:
        raise EncryptionError("Failed to decrypt API key.") from exc


def mask_api_key(api_key: str) -> str:
    """Returns a safe, masked representation of an API key for UI display."""
    clean = api_key.strip()
    if len(clean) <= 8:
        return "••••" + clean[-2:] if len(clean) >= 2 else "••••"
    return f"{clean[:4]}••••••••{clean[-4:]}"
