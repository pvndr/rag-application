from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


@dataclass(frozen=True)
class Document:
    filename: str
    text: str
    content_type: str
    file_path: str
    size_bytes: int
    user_id: str
    chunk_count: int = 0
    status: str = "indexed"
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class Chunk:
    id: str
    document_id: str
    filename: str
    text: str
    metadata: dict[str, str | int | float] = field(default_factory=dict)
    score: float = 0.0


@dataclass(frozen=True)
class Citation:
    document_id: str
    filename: str
    chunk_id: str
    text: str
    score: float
    metadata: dict[str, str | int | float] = field(default_factory=dict)


@dataclass(frozen=True)
class SourceReference:
    document: str
    page: int | None = None


@dataclass(frozen=True)
class StructuredRagResponse:
    answer: str
    summary: str
    key_points: list[str] = field(default_factory=list)
    sources: list[SourceReference] = field(default_factory=list)
    confidence: str = "Low"
    follow_up_questions: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RagAnswer:
    response: StructuredRagResponse
    citations: list[Citation]


@dataclass(frozen=True)
class ConversationMessage:
    role: str
    content: str
    chat_id: str | None = None
    structured: dict | None = None
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class ConversationSession:
    id: str
    user_id: str
    title: str
    messages: list[ConversationMessage] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class User:
    id: str
    name: str
    email: str
    password_hash: str
    role: str = "user"
    is_verified: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class ProviderCredential:
    id: str
    user_id: str
    provider: str
    masked_key: str
    encrypted_key: str
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
