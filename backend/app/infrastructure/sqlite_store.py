import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.domain.entities import ConversationMessage, ConversationSession, Document, ProviderCredential, User
from app.domain.repositories import ConversationRepository, DocumentRepository, ProviderCredentialRepository


class SqliteStore:
    def __init__(self, database_path: str) -> None:
        self._path = Path(database_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _init_db(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'user',
                    is_verified INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS refresh_tokens (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    token_hash TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    revoked_at TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS password_reset_tokens (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    token_hash TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    used_at TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    filename TEXT NOT NULL,
                    text TEXT NOT NULL,
                    content_type TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    chunk_count INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS chats (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    chat_id TEXT NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
                    role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                    content TEXT NOT NULL,
                    structured_json TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS provider_credentials (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    provider TEXT NOT NULL,
                    masked_key TEXT NOT NULL,
                    encrypted_key TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(user_id, provider)
                );

                CREATE INDEX IF NOT EXISTS idx_documents_user ON documents(user_id);
                CREATE INDEX IF NOT EXISTS idx_chats_user ON chats(user_id);
                CREATE INDEX IF NOT EXISTS idx_messages_chat ON messages(chat_id, created_at);
                CREATE INDEX IF NOT EXISTS idx_provider_credentials_user ON provider_credentials(user_id);
                """
            )
        with self.connect() as conn:
            # Databases created before structured assistant responses existed
            # lack the column; add it in place without touching existing rows.
            columns = {str(row["name"]) for row in conn.execute("PRAGMA table_info(messages)")}
            if "structured_json" not in columns:
                conn.execute("ALTER TABLE messages ADD COLUMN structured_json TEXT")


class SqliteUserRepository:
    def __init__(self, store: SqliteStore) -> None:
        self._store = store

    def create(self, name: str, email: str, password_hash: str, role: str = "user") -> User:
        user = User(
            id=str(uuid4()),
            name=name,
            email=email.lower(),
            password_hash=password_hash,
            role=role,
        )
        with self._store.connect() as conn:
            conn.execute(
                """
                INSERT INTO users (id, name, email, password_hash, role, is_verified, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user.id,
                    user.name,
                    user.email,
                    user.password_hash,
                    user.role,
                    int(user.is_verified),
                    user.created_at.isoformat(),
                ),
            )
        return user

    def get(self, user_id: str) -> User | None:
        with self._store.connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return _user_from_row(row) if row else None

    def get_by_email(self, email: str) -> User | None:
        with self._store.connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE email = ?", (email.lower(),)).fetchone()
        return _user_from_row(row) if row else None

    def update_password(self, user_id: str, password_hash: str) -> None:
        with self._store.connect() as conn:
            conn.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (password_hash, user_id),
            )


class SqliteTokenRepository:
    def __init__(self, store: SqliteStore) -> None:
        self._store = store

    def save_refresh_token(self, token_id: str, user_id: str, token_hash: str, expires_at: datetime) -> None:
        with self._store.connect() as conn:
            conn.execute(
                """
                INSERT INTO refresh_tokens (id, user_id, token_hash, expires_at, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (token_id, user_id, token_hash, expires_at.isoformat(), _now()),
            )

    def get_refresh_token(self, token_id: str) -> sqlite3.Row | None:
        with self._store.connect() as conn:
            return conn.execute(
                "SELECT * FROM refresh_tokens WHERE id = ?",
                (token_id,),
            ).fetchone()

    def revoke_refresh_token(self, token_id: str) -> None:
        with self._store.connect() as conn:
            conn.execute(
                "UPDATE refresh_tokens SET revoked_at = ? WHERE id = ?",
                (_now(), token_id),
            )

    def create_password_reset(self, user_id: str, token_hash: str, expires_at: datetime) -> str:
        token_id = str(uuid4())
        with self._store.connect() as conn:
            conn.execute(
                """
                INSERT INTO password_reset_tokens (id, user_id, token_hash, expires_at, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (token_id, user_id, token_hash, expires_at.isoformat(), _now()),
            )
        return token_id

    def get_password_reset(self, token_id: str) -> sqlite3.Row | None:
        with self._store.connect() as conn:
            return conn.execute(
                "SELECT * FROM password_reset_tokens WHERE id = ?",
                (token_id,),
            ).fetchone()

    def mark_password_reset_used(self, token_id: str) -> None:
        with self._store.connect() as conn:
            conn.execute(
                "UPDATE password_reset_tokens SET used_at = ? WHERE id = ?",
                (_now(), token_id),
            )


class SqliteDocumentRepository(DocumentRepository):
    def __init__(self, store: SqliteStore) -> None:
        self._store = store

    def add(self, document: Document) -> Document:
        with self._store.connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO documents
                (id, user_id, filename, text, content_type, file_path, size_bytes, chunk_count, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    document.id,
                    document.user_id,
                    document.filename,
                    document.text,
                    document.content_type,
                    document.file_path,
                    document.size_bytes,
                    document.chunk_count,
                    document.status,
                    document.created_at.isoformat(),
                ),
            )
        return document

    def list(self, user_id: str) -> list[Document]:
        with self._store.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM documents WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
        return [_document_from_row(row) for row in rows]

    def get(self, document_id: str, user_id: str) -> Document | None:
        with self._store.connect() as conn:
            row = conn.execute(
                "SELECT * FROM documents WHERE id = ? AND user_id = ?",
                (document_id, user_id),
            ).fetchone()
        return _document_from_row(row) if row else None

    def delete(self, document_id: str, user_id: str) -> None:
        with self._store.connect() as conn:
            conn.execute(
                "DELETE FROM documents WHERE id = ? AND user_id = ?",
                (document_id, user_id),
            )


class SqliteConversationRepository(ConversationRepository):
    def __init__(self, store: SqliteStore) -> None:
        self._store = store

    def list_sessions(self, user_id: str) -> list[ConversationSession]:
        with self._store.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM chats WHERE user_id = ? ORDER BY updated_at DESC",
                (user_id,),
            ).fetchall()
        return [self._session_from_row(row) for row in rows]

    def get_or_create(
        self,
        session_id: str,
        user_id: str,
        title: str | None = None,
    ) -> ConversationSession:
        with self._store.connect() as conn:
            row = conn.execute(
                "SELECT * FROM chats WHERE id = ? AND user_id = ?",
                (session_id, user_id),
            ).fetchone()
            if row is None:
                now = _now()
                conn.execute(
                    """
                    INSERT INTO chats (id, user_id, title, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (session_id, user_id, title or "New conversation", now, now),
                )
                row = conn.execute(
                    "SELECT * FROM chats WHERE id = ? AND user_id = ?",
                    (session_id, user_id),
                ).fetchone()
        return self._session_from_row(row)

    def append_message(
        self,
        session_id: str,
        user_id: str,
        role: str,
        content: str,
        title: str | None = None,
        structured: dict | None = None,
    ) -> ConversationMessage:
        session = self.get_or_create(session_id, user_id, title=title)
        message = ConversationMessage(
            role=role,
            content=content,
            chat_id=session.id,
            structured=structured,
        )
        with self._store.connect() as conn:
            conn.execute(
                """
                INSERT INTO messages (id, chat_id, role, content, structured_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    message.id,
                    session.id,
                    message.role,
                    message.content,
                    json.dumps(message.structured) if message.structured is not None else None,
                    message.created_at.isoformat(),
                ),
            )
            if title and session.title == "New conversation":
                conn.execute(
                    "UPDATE chats SET title = ?, updated_at = ? WHERE id = ? AND user_id = ?",
                    (title, _now(), session.id, user_id),
                )
            else:
                conn.execute(
                    "UPDATE chats SET updated_at = ? WHERE id = ? AND user_id = ?",
                    (_now(), session.id, user_id),
                )
        return message

    def list_messages(self, session_id: str, user_id: str, limit: int = 8) -> list[ConversationMessage]:
        with self._store.connect() as conn:
            rows = conn.execute(
                """
                SELECT messages.* FROM messages
                JOIN chats ON chats.id = messages.chat_id
                WHERE messages.chat_id = ? AND chats.user_id = ?
                ORDER BY messages.created_at DESC
                LIMIT ?
                """,
                (session_id, user_id, limit),
            ).fetchall()
        return [_message_from_row(row) for row in reversed(rows)]

    def rename(self, session_id: str, user_id: str, title: str) -> ConversationSession:
        self.get_or_create(session_id, user_id, title=title)
        with self._store.connect() as conn:
            conn.execute(
                "UPDATE chats SET title = ?, updated_at = ? WHERE id = ? AND user_id = ?",
                (title, _now(), session_id, user_id),
            )
        return self.get_or_create(session_id, user_id)

    def delete(self, session_id: str, user_id: str) -> None:
        with self._store.connect() as conn:
            conn.execute("DELETE FROM chats WHERE id = ? AND user_id = ?", (session_id, user_id))

    def _session_from_row(self, row: sqlite3.Row) -> ConversationSession:
        return ConversationSession(
            id=str(row["id"]),
            user_id=str(row["user_id"]),
            title=str(row["title"]),
            messages=self.list_messages(str(row["id"]), str(row["user_id"]), limit=200),
            created_at=datetime.fromisoformat(str(row["created_at"])),
            updated_at=datetime.fromisoformat(str(row["updated_at"])),
        )


def _document_from_row(row: sqlite3.Row) -> Document:
    return Document(
        id=str(row["id"]),
        user_id=str(row["user_id"]),
        filename=str(row["filename"]),
        text=str(row["text"]),
        content_type=str(row["content_type"]),
        file_path=str(row["file_path"]),
        size_bytes=int(row["size_bytes"]),
        chunk_count=int(row["chunk_count"]),
        status=str(row["status"]),
        created_at=datetime.fromisoformat(str(row["created_at"])),
    )


def _message_from_row(row: sqlite3.Row) -> ConversationMessage:
    return ConversationMessage(
        id=str(row["id"]),
        chat_id=str(row["chat_id"]),
        role=str(row["role"]),
        content=str(row["content"]),
        structured=json.loads(row["structured_json"]) if row["structured_json"] else None,
        created_at=datetime.fromisoformat(str(row["created_at"])),
    )


def _user_from_row(row: sqlite3.Row) -> User:
    return User(
        id=str(row["id"]),
        name=str(row["name"]),
        email=str(row["email"]),
        password_hash=str(row["password_hash"]),
        role=str(row["role"]),
        is_verified=bool(row["is_verified"]),
        created_at=datetime.fromisoformat(str(row["created_at"])),
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SqliteProviderCredentialRepository(ProviderCredentialRepository):
    def __init__(self, store: SqliteStore) -> None:
        self._store = store

    def save(self, credential: ProviderCredential) -> ProviderCredential:
        with self._store.connect() as conn:
            conn.execute(
                """
                INSERT INTO provider_credentials (
                    id, user_id, provider, masked_key, encrypted_key, is_active, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, provider) DO UPDATE SET
                    masked_key = excluded.masked_key,
                    encrypted_key = excluded.encrypted_key,
                    is_active = excluded.is_active,
                    updated_at = excluded.updated_at
                """,
                (
                    credential.id,
                    credential.user_id,
                    credential.provider,
                    credential.masked_key,
                    credential.encrypted_key,
                    int(credential.is_active),
                    credential.created_at.isoformat(),
                    credential.updated_at.isoformat(),
                ),
            )
        return credential

    def get(self, user_id: str, provider: str) -> ProviderCredential | None:
        with self._store.connect() as conn:
            row = conn.execute(
                """
                SELECT id, user_id, provider, masked_key, encrypted_key, is_active, created_at, updated_at
                FROM provider_credentials
                WHERE user_id = ? AND provider = ?
                """,
                (user_id, provider),
            ).fetchone()
            if row is None:
                return None
            return self._row_to_credential(row)

    def list(self, user_id: str) -> list[ProviderCredential]:
        with self._store.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, user_id, provider, masked_key, encrypted_key, is_active, created_at, updated_at
                FROM provider_credentials
                WHERE user_id = ?
                ORDER BY created_at ASC
                """,
                (user_id,),
            ).fetchall()
            return [self._row_to_credential(row) for row in rows]

    def delete(self, user_id: str, provider: str) -> None:
        with self._store.connect() as conn:
            conn.execute(
                "DELETE FROM provider_credentials WHERE user_id = ? AND provider = ?",
                (user_id, provider),
            )

    @staticmethod
    def _row_to_credential(row: sqlite3.Row) -> ProviderCredential:
        return ProviderCredential(
            id=str(row["id"]),
            user_id=str(row["user_id"]),
            provider=str(row["provider"]),
            masked_key=str(row["masked_key"]),
            encrypted_key=str(row["encrypted_key"]),
            is_active=bool(row["is_active"]),
            created_at=datetime.fromisoformat(str(row["created_at"])),
            updated_at=datetime.fromisoformat(str(row["updated_at"])),
        )
