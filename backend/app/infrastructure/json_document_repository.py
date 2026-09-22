import json
from datetime import datetime
from pathlib import Path

from app.domain.entities import Document
from app.domain.repositories import DocumentRepository


class JsonDocumentRepository(DocumentRepository):
    def __init__(self, metadata_path: str) -> None:
        self._metadata_path = Path(metadata_path)
        self._metadata_path.parent.mkdir(parents=True, exist_ok=True)
        if not self._metadata_path.exists():
            self._write({})

    def add(self, document: Document) -> Document:
        documents = self._read()
        documents[document.id] = _to_record(document)
        self._write(documents)
        return document

    def list(self) -> list[Document]:
        documents = [_from_record(record) for record in self._read().values()]
        return sorted(documents, key=lambda document: document.created_at, reverse=True)

    def get(self, document_id: str) -> Document | None:
        record = self._read().get(document_id)
        return _from_record(record) if record else None

    def delete(self, document_id: str) -> None:
        documents = self._read()
        documents.pop(document_id, None)
        self._write(documents)

    def _read(self) -> dict[str, dict[str, object]]:
        return json.loads(self._metadata_path.read_text(encoding="utf-8"))

    def _write(self, documents: dict[str, dict[str, object]]) -> None:
        self._metadata_path.write_text(
            json.dumps(documents, indent=2, sort_keys=True),
            encoding="utf-8",
        )


def _to_record(document: Document) -> dict[str, object]:
    return {
        "id": document.id,
        "filename": document.filename,
        "text": document.text,
        "content_type": document.content_type,
        "file_path": document.file_path,
        "size_bytes": document.size_bytes,
        "chunk_count": document.chunk_count,
        "status": document.status,
        "created_at": document.created_at.isoformat(),
    }


def _from_record(record: dict[str, object]) -> Document:
    return Document(
        id=str(record["id"]),
        filename=str(record["filename"]),
        text=str(record["text"]),
        content_type=str(record["content_type"]),
        file_path=str(record["file_path"]),
        size_bytes=int(record["size_bytes"]),
        chunk_count=int(record["chunk_count"]),
        status=str(record["status"]),
        created_at=datetime.fromisoformat(str(record["created_at"])),
    )
