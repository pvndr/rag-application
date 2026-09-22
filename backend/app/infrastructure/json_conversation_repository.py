import json
from datetime import datetime, timezone
from pathlib import Path

from app.domain.entities import ConversationMessage, ConversationSession
from app.domain.repositories import ConversationRepository


class JsonConversationRepository(ConversationRepository):
    def __init__(self, path: str) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            self._write({})

    def get_or_create(self, session_id: str, title: str | None = None) -> ConversationSession:
        sessions = self._read()
        if session_id not in sessions:
            now = datetime.now(timezone.utc).isoformat()
            sessions[session_id] = {
                "id": session_id,
                "title": title or "New conversation",
                "messages": [],
                "created_at": now,
                "updated_at": now,
            }
            self._write(sessions)
        return _from_record(sessions[session_id])

    def append_message(
        self,
        session_id: str,
        role: str,
        content: str,
        title: str | None = None,
    ) -> ConversationMessage:
        sessions = self._read()
        session = self.get_or_create(session_id, title=title)
        sessions = self._read()
        record = sessions[session.id]
        message = ConversationMessage(role=role, content=content)
        record["messages"].append(_message_to_record(message))
        if title and record["title"] == "New conversation":
            record["title"] = title
        record["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._write(sessions)
        return message

    def list_messages(self, session_id: str, limit: int = 8) -> list[ConversationMessage]:
        session = self.get_or_create(session_id)
        return session.messages[-limit:]

    def rename(self, session_id: str, title: str) -> ConversationSession:
        sessions = self._read()
        session = self.get_or_create(session_id, title=title)
        sessions = self._read()
        sessions[session.id]["title"] = title
        sessions[session.id]["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._write(sessions)
        return _from_record(sessions[session.id])

    def _read(self) -> dict[str, dict[str, object]]:
        return json.loads(self._path.read_text(encoding="utf-8"))

    def _write(self, sessions: dict[str, dict[str, object]]) -> None:
        self._path.write_text(json.dumps(sessions, indent=2, sort_keys=True), encoding="utf-8")


def _message_to_record(message: ConversationMessage) -> dict[str, str]:
    return {
        "id": message.id,
        "role": message.role,
        "content": message.content,
        "created_at": message.created_at.isoformat(),
    }


def _message_from_record(record: dict[str, str]) -> ConversationMessage:
    return ConversationMessage(
        id=record["id"],
        role=record["role"],
        content=record["content"],
        created_at=datetime.fromisoformat(record["created_at"]),
    )


def _from_record(record: dict[str, object]) -> ConversationSession:
    return ConversationSession(
        id=str(record["id"]),
        title=str(record["title"]),
        messages=[
            _message_from_record(message)
            for message in record.get("messages", [])
        ],
        created_at=datetime.fromisoformat(str(record["created_at"])),
        updated_at=datetime.fromisoformat(str(record["updated_at"])),
    )
