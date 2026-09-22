from functools import lru_cache

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.application.auth_service import AuthError, AuthService
from app.application.provider_service import ProviderService
from app.application.rag_service import RagService
from app.core.config import settings
from app.domain.entities import User
from app.domain.repositories import AnswerGeneratorFactory
from app.infrastructure.answer_generator_factory import DynamicAnswerGeneratorFactory
from app.infrastructure.chroma_retriever import ChromaRetriever
from app.infrastructure.document_extractors import MultiFormatDocumentExtractor
from app.infrastructure.embedding_provider import SentenceTransformerEmbeddingProvider
from app.infrastructure.email_sender import SendGridEmailSender
from app.infrastructure.local_file_storage import LocalFileStorage
from app.infrastructure.semantic_chunker import SemanticTextChunker
from app.infrastructure.sqlite_store import (
    SqliteConversationRepository,
    SqliteDocumentRepository,
    SqliteProviderCredentialRepository,
    SqliteStore,
    SqliteTokenRepository,
    SqliteUserRepository,
)

bearer_scheme = HTTPBearer(auto_error=False)


@lru_cache
def get_store() -> SqliteStore:
    return SqliteStore(settings.database_path)


@lru_cache
def get_auth_service() -> AuthService:
    store = get_store()
    return AuthService(
        users=SqliteUserRepository(store),
        tokens=SqliteTokenRepository(store),
        email_sender=SendGridEmailSender(
            api_key=settings.sendgrid_api_key,
            from_email=settings.sendgrid_from_email,
            app_name=settings.app_name,
        ),
    )


@lru_cache
def get_provider_credential_repository() -> SqliteProviderCredentialRepository:
    return SqliteProviderCredentialRepository(get_store())


@lru_cache
def get_answer_generator_factory() -> AnswerGeneratorFactory:
    return DynamicAnswerGeneratorFactory(
        credentials=get_provider_credential_repository(),
        fallback_gemini_api_key=settings.gemini_api_key,
        gemini_model=settings.gemini_model,
        gemini_temperature=settings.gemini_temperature,
        gemini_max_output_tokens=settings.gemini_max_output_tokens,
    )


@lru_cache
def get_provider_service() -> ProviderService:
    return ProviderService(
        credentials=get_provider_credential_repository(),
        fallback_gemini_api_key=settings.gemini_api_key,
    )


@lru_cache
def get_rag_service() -> RagService:
    store = get_store()
    embedding_provider = SentenceTransformerEmbeddingProvider(
        settings.embedding_model,
        cache_folder=settings.embedding_cache_folder,
    )
    return RagService(
        documents=SqliteDocumentRepository(store),
        conversations=SqliteConversationRepository(store),
        retriever=ChromaRetriever(
            persist_path=settings.chroma_path,
            collection_name=settings.chroma_collection,
            embedding_provider=embedding_provider,
        ),
        answer_generator=get_answer_generator_factory(),
        extractor=MultiFormatDocumentExtractor(),
        file_storage=LocalFileStorage(settings.upload_dir),
        text_chunker=SemanticTextChunker(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        ),
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    auth_service: AuthService = Depends(get_auth_service),
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return auth_service.get_user_from_access_token(credentials.credentials)
    except AuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required.")
    return user
