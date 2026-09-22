from abc import ABC, abstractmethod

from pathlib import Path

from app.domain.entities import (
    Chunk,
    ConversationMessage,
    ConversationSession,
    Document,
    ProviderCredential,
    StructuredRagResponse,
)


class DocumentRepository(ABC):
    @abstractmethod
    def add(self, document: Document) -> Document:
        raise NotImplementedError

    @abstractmethod
    def list(self, user_id: str) -> list[Document]:
        raise NotImplementedError

    @abstractmethod
    def get(self, document_id: str, user_id: str) -> Document | None:
        raise NotImplementedError

    @abstractmethod
    def delete(self, document_id: str, user_id: str) -> None:
        raise NotImplementedError


class Retriever(ABC):
    @abstractmethod
    def index(self, document: Document, chunks: list[Chunk]) -> None:
        raise NotImplementedError

    @abstractmethod
    def remove_document(self, document_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def search(self, query: str, user_id: str, limit: int = 4) -> list[Chunk]:
        raise NotImplementedError


class AnswerGenerator(ABC):
    @abstractmethod
    def generate(
        self,
        question: str,
        chunks: list[Chunk],
        history: list[ConversationMessage] | None = None,
    ) -> StructuredRagResponse:
        raise NotImplementedError


class DocumentExtractor(ABC):
    @abstractmethod
    def extract(self, file_path: Path, content_type: str) -> str:
        raise NotImplementedError


class FileStorage(ABC):
    @abstractmethod
    def save(self, filename: str, contents: bytes) -> Path:
        raise NotImplementedError

    @abstractmethod
    def delete(self, file_path: str) -> None:
        raise NotImplementedError


class TextChunker(ABC):
    @abstractmethod
    def chunk(self, document: Document) -> list[Chunk]:
        raise NotImplementedError


class ConversationRepository(ABC):
    @abstractmethod
    def list_sessions(self, user_id: str) -> list[ConversationSession]:
        raise NotImplementedError

    @abstractmethod
    def get_or_create(
        self,
        session_id: str,
        user_id: str,
        title: str | None = None,
    ) -> ConversationSession:
        raise NotImplementedError

    @abstractmethod
    def append_message(
        self,
        session_id: str,
        user_id: str,
        role: str,
        content: str,
        title: str | None = None,
        structured: dict | None = None,
    ) -> ConversationMessage:
        raise NotImplementedError

    @abstractmethod
    def list_messages(self, session_id: str, user_id: str, limit: int = 8) -> list[ConversationMessage]:
        raise NotImplementedError

    @abstractmethod
    def rename(self, session_id: str, user_id: str, title: str) -> ConversationSession:
        raise NotImplementedError

    @abstractmethod
    def delete(self, session_id: str, user_id: str) -> None:
        raise NotImplementedError


class ProviderCredentialRepository(ABC):
    @abstractmethod
    def save(self, credential: ProviderCredential) -> ProviderCredential:
        raise NotImplementedError

    @abstractmethod
    def get(self, user_id: str, provider: str) -> ProviderCredential | None:
        raise NotImplementedError

    @abstractmethod
    def list(self, user_id: str) -> list[ProviderCredential]:
        raise NotImplementedError

    @abstractmethod
    def delete(self, user_id: str, provider: str) -> None:
        raise NotImplementedError


class AnswerGeneratorFactory(ABC):
    @abstractmethod
    def get_generator_for_user(self, user_id: str) -> AnswerGenerator:
        raise NotImplementedError
