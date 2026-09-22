import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.domain.entities import User
from app.infrastructure.sqlite_store import (
    SqliteConversationRepository,
    SqliteStore,
    SqliteUserRepository,
)

STRUCTURED = {
    "answer": "Embeddings are stored in ChromaDB.",
    "summary": "ChromaDB persists chunk embeddings.",
    "key_points": ["ChromaDB stores chunk embeddings", "Each user sees only their chunks"],
    "sources": [{"document": "sample.txt", "page": None}],
    "confidence": "High",
    "follow_up_questions": ["Where are original files stored?"],
}


class StructuredMessagePersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self._tmp.cleanup)
        self._db_path = Path(self._tmp.name) / "test.sqlite3"
        store = SqliteStore(str(self._db_path))
        self.user = SqliteUserRepository(store).create(
            name="Persist Test", email=f"{uuid4().hex[:8]}@example.com", password_hash="x"
        )
        self.conversations = SqliteConversationRepository(store)

    def test_assistant_structured_metadata_roundtrip(self) -> None:
        self.conversations.append_message("s1", self.user.id, role="user", content="question")
        self.conversations.append_message(
            "s1", self.user.id, role="assistant", content=STRUCTURED["answer"], structured=STRUCTURED
        )

        messages = self.conversations.list_messages("s1", self.user.id)
        self.assertEqual([m.role for m in messages], ["user", "assistant"])
        self.assertIsNone(messages[0].structured)
        self.assertEqual(messages[1].structured, STRUCTURED)
        self.assertEqual(messages[1].content, STRUCTURED["answer"])

    def test_message_without_structured_metadata_stays_none(self) -> None:
        self.conversations.append_message("s2", self.user.id, role="assistant", content="plain")
        (message,) = self.conversations.list_messages("s2", self.user.id)
        self.assertIsNone(message.structured)

    def test_legacy_row_without_column_value_loads_as_none(self) -> None:
        # Simulate a row written before structured metadata existed by
        # inserting directly without the structured_json value.
        session = self.conversations.get_or_create("s3", self.user.id)
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT INTO messages (id, chat_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
                (str(uuid4()), session.id, "assistant", "legacy answer", datetime.now(timezone.utc).isoformat()),
            )
        messages = self.conversations.list_messages("s3", self.user.id)
        self.assertEqual(len(messages), 1)
        self.assertIsNone(messages[0].structured)

    def test_migration_adds_column_to_legacy_database(self) -> None:
        # Build a database with the pre-structured messages schema, then open
        # it through SqliteStore: the migration must add the column in place
        # and preserve existing rows.
        legacy_path = Path(self._tmp.name) / "legacy.sqlite3"
        conn = sqlite3.connect(legacy_path)
        conn.executescript(
            """
            CREATE TABLE users (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'user',
                is_verified INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL
            );
            CREATE TABLE chats (
                id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                title TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE messages (
                id TEXT PRIMARY KEY,
                chat_id TEXT NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
                role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            INSERT INTO users VALUES ('u1', 'Old User', 'old@example.com', 'h', 'user', 0, '2025-01-01T00:00:00');
            INSERT INTO chats VALUES ('c1', 'u1', 'Legacy chat', '2025-01-01T00:00:00', '2025-01-01T00:00:00');
            INSERT INTO messages VALUES ('m1', 'c1', 'assistant', 'old answer', '2025-01-01T00:00:00');
            """
        )
        conn.commit()
        conn.close()

        store = SqliteStore(str(legacy_path))
        conversations = SqliteConversationRepository(store)
        legacy_messages = conversations.list_messages("c1", "u1")
        self.assertEqual(len(legacy_messages), 1)
        self.assertEqual(legacy_messages[0].content, "old answer")
        self.assertIsNone(legacy_messages[0].structured)

        # New messages with structured metadata can be appended and restored.
        conversations.append_message(
            "c1", "u1", role="assistant", content=STRUCTURED["answer"], structured=STRUCTURED
        )
        (new_message,) = [
            m for m in conversations.list_messages("c1", "u1") if m.content == STRUCTURED["answer"]
        ]
        self.assertEqual(new_message.structured, STRUCTURED)

    def test_structured_json_is_valid_json_in_storage(self) -> None:
        self.conversations.append_message(
            "s4", self.user.id, role="assistant", content=STRUCTURED["answer"], structured=STRUCTURED
        )
        with sqlite3.connect(self._db_path) as conn:
            (raw,) = conn.execute(
                "SELECT structured_json FROM messages WHERE chat_id = ?", ("s4",)
            ).fetchone()
        self.assertEqual(json.loads(raw), STRUCTURED)


if __name__ == "__main__":
    unittest.main()
