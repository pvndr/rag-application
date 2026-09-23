import logging

from app.application.errors import AnswerGenerationError
from app.core.security import decrypt_api_key
from app.domain.repositories import AnswerGenerator, AnswerGeneratorFactory, ProviderCredentialRepository
from app.infrastructure.gemini_answer_generator import GeminiAnswerGenerator

logger = logging.getLogger(__name__)


class DynamicAnswerGeneratorFactory(AnswerGeneratorFactory):
    def __init__(
        self,
        credentials: ProviderCredentialRepository,
        fallback_gemini_api_key: str | None,
        gemini_model: str,
        gemini_temperature: float,
        gemini_max_output_tokens: int,
    ) -> None:
        self._credentials = credentials
        self._fallback_gemini_api_key = (
            fallback_gemini_api_key.strip() if fallback_gemini_api_key else None
        )
        self._gemini_model = (
            gemini_model.strip() if gemini_model else "gemini-2.5-flash"
        )
        self._gemini_temperature = gemini_temperature
        self._gemini_max_output_tokens = gemini_max_output_tokens

    def get_generator_for_user(self, user_id: str, provider: str = "gemini") -> AnswerGenerator:
        """Resolves an AnswerGenerator for the given user and provider.

        Currently implements Gemini. Extensible for OpenAI/Anthropic/OpenRouter later.
        Plaintext keys are never logged or persisted.
        """
        if provider == "gemini":
            return self._build_gemini_generator(user_id)
        raise AnswerGenerationError(f"Unsupported LLM provider: '{provider}'.")

    def _build_gemini_generator(self, user_id: str) -> GeminiAnswerGenerator:
        cred = self._credentials.get(user_id=user_id, provider="gemini")
        api_key: str | None = None

        if cred and cred.is_active:
            try:
                decrypted = decrypt_api_key(cred.encrypted_key)
                api_key = decrypted.strip() if decrypted else None
            except Exception as exc:
                logger.error("Failed to decrypt Gemini API key for user %s", user_id)
                raise AnswerGenerationError(
                    "Could not decrypt stored Gemini API key. Please reconfigure your API key in Settings."
                ) from exc

        if not api_key:
            api_key = self._fallback_gemini_api_key

        if not api_key:
            raise AnswerGenerationError(
                "No API key configured for Gemini. Please add your API key in Settings."
            )

        return GeminiAnswerGenerator(
            api_key=api_key.strip() if api_key else None,
            model=self._gemini_model.strip() if self._gemini_model else "gemini-2.5-flash",
            temperature=self._gemini_temperature,
            max_output_tokens=self._gemini_max_output_tokens,
        )
