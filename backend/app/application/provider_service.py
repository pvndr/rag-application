from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from app.core.security import encrypt_api_key, mask_api_key
from app.domain.entities import ProviderCredential
from app.domain.repositories import ProviderCredentialRepository

SUPPORTED_PROVIDERS = {"gemini"}


class ProviderServiceError(Exception):
    pass


@dataclass(frozen=True)
class ProviderStatus:
    provider: str
    masked_key: str | None
    is_configured: bool
    is_custom: bool
    has_system_fallback: bool
    updated_at: datetime | None


class ProviderService:
    def __init__(
        self,
        credentials: ProviderCredentialRepository,
        fallback_gemini_api_key: str | None = None,
    ) -> None:
        self._credentials = credentials
        self._fallback_gemini_api_key = fallback_gemini_api_key

    def list_provider_statuses(self, user_id: str) -> list[ProviderStatus]:
        """Returns provider statuses for the user with masked keys only."""
        custom_creds = {cred.provider: cred for cred in self._credentials.list(user_id)}
        statuses: list[ProviderStatus] = []

        for provider in sorted(SUPPORTED_PROVIDERS):
            cred = custom_creds.get(provider)
            has_fallback = bool(self._fallback_gemini_api_key) if provider == "gemini" else False

            if cred and cred.is_active:
                statuses.append(
                    ProviderStatus(
                        provider=provider,
                        masked_key=cred.masked_key,
                        is_configured=True,
                        is_custom=True,
                        has_system_fallback=has_fallback,
                        updated_at=cred.updated_at,
                    )
                )
            else:
                statuses.append(
                    ProviderStatus(
                        provider=provider,
                        masked_key=None,
                        is_configured=has_fallback,
                        is_custom=False,
                        has_system_fallback=has_fallback,
                        updated_at=None,
                    )
                )
        return statuses

    def save_provider_key(self, user_id: str, provider: str, api_key: str) -> ProviderStatus:
        """Saves an encrypted provider API key. Plaintext key is never logged or returned."""
        provider_clean = provider.strip().lower()
        if provider_clean not in SUPPORTED_PROVIDERS:
            raise ProviderServiceError(
                f"Provider '{provider}' is not supported. Currently supported providers: {', '.join(sorted(SUPPORTED_PROVIDERS))}."
            )

        key_clean = api_key.strip()
        if not key_clean:
            raise ProviderServiceError("API key cannot be empty.")

        now = datetime.now(timezone.utc)
        encrypted = encrypt_api_key(key_clean)
        masked = mask_api_key(key_clean)

        existing = self._credentials.get(user_id, provider_clean)
        record_id = existing.id if existing else str(uuid4())
        created_at = existing.created_at if existing else now

        credential = ProviderCredential(
            id=record_id,
            user_id=user_id,
            provider=provider_clean,
            masked_key=masked,
            encrypted_key=encrypted,
            is_active=True,
            created_at=created_at,
            updated_at=now,
        )
        self._credentials.save(credential)

        has_fallback = bool(self._fallback_gemini_api_key) if provider_clean == "gemini" else False
        return ProviderStatus(
            provider=provider_clean,
            masked_key=masked,
            is_configured=True,
            is_custom=True,
            has_system_fallback=has_fallback,
            updated_at=now,
        )

    def delete_provider_key(self, user_id: str, provider: str) -> None:
        """Deletes custom provider credentials for the user."""
        provider_clean = provider.strip().lower()
        if provider_clean not in SUPPORTED_PROVIDERS:
            raise ProviderServiceError(f"Provider '{provider}' is not supported.")
        self._credentials.delete(user_id, provider_clean)
