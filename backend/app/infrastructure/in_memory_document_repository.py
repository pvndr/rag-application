from app.domain.entities import Document
from app.domain.repositories import DocumentRepository


class InMemoryDocumentRepository(DocumentRepository):
    def __init__(self) -> None:
        self._documents: dict[str, Document] = {}

    def add(self, document: Document) -> Document:
        self._documents[document.id] = document
        return document

    def list(self) -> list[Document]:
        return sorted(
            self._documents.values(),
            key=lambda document: document.created_at,
            reverse=True,
        )

    def get(self, document_id: str) -> Document | None:
        return self._documents.get(document_id)

    def delete(self, document_id: str) -> None:
        self._documents.pop(document_id, None)
