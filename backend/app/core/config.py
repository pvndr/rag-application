from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict  # type: ignore


class Settings(BaseSettings):
    app_name: str = "RAG Starter API"
    environment: str = "development"
    frontend_origins_raw: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        alias="FRONTEND_ORIGINS",
    )
    max_upload_bytes: int = 2_097_152
    chunk_size: int = 900
    chunk_overlap: int = 120
    upload_dir: str = "storage/uploads"
    metadata_path: str = "storage/documents.json"
    conversations_path: str = "storage/conversations.json"
    chroma_path: str = "storage/chroma"
    chroma_collection: str = "rag_documents"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_cache_folder: str | None = None
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    gemini_temperature: float = 0.2
    gemini_max_output_tokens: int = 1024
    database_path: str = "storage/rag.sqlite3"
    jwt_secret_key: str = "change-me-in-production"
    jwt_issuer: str = "rag-starter"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 14
    password_reset_token_expire_minutes: int = 30
    app_base_url: str = "http://127.0.0.1:5173"
    sendgrid_api_key: str | None = None
    sendgrid_from_email: str = "RAG Starter <noreply@example.com>"
    provider_encryption_key: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        populate_by_name=True,
    )

    @property
    def frontend_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.frontend_origins_raw.split(",")
            if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
