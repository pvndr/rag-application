from pathlib import Path

from app.domain.entities import Citation, Document, RagAnswer, StructuredRagResponse
from app.domain.repositories import (
    AnswerGenerator,
    AnswerGeneratorFactory,
    ConversationRepository,
    DocumentExtractor,
    DocumentRepository,
    FileStorage,
    Retriever,
    TextChunker,
)


class RagService:
    def __init__(
        self,
        documents: DocumentRepository,
        conversations: ConversationRepository,
        retriever: Retriever,
        answer_generator: AnswerGenerator | AnswerGeneratorFactory,
        extractor: DocumentExtractor,
        file_storage: FileStorage,
        text_chunker: TextChunker,
    ) -> None:
        self._documents = documents
        self._conversations = conversations
        self._retriever = retriever
        self._answer_generator = answer_generator
        self._extractor = extractor
        self._file_storage = file_storage
        self._text_chunker = text_chunker

    def ingest_document(
        self,
        user_id: str,
        filename: str,
        content_type: str,
        contents: bytes,
    ) -> Document:
        file_path = self._file_storage.save(filename, contents)
        try:
            text = self._extractor.extract(file_path, content_type)
            document = Document(
                filename=filename,
                text=text,
                content_type=content_type,
                file_path=str(file_path),
                size_bytes=len(contents),
                user_id=user_id,
            )
            chunks = self._text_chunker.chunk(document)
            indexed_document = Document(
                id=document.id,
                filename=document.filename,
                text=document.text,
                content_type=document.content_type,
                file_path=document.file_path,
                size_bytes=document.size_bytes,
                user_id=document.user_id,
                chunk_count=len(chunks),
                status="indexed",
                created_at=document.created_at,
            )
            self._retriever.index(indexed_document, chunks)
            self._documents.add(indexed_document)
            return indexed_document
        except Exception:
            self._file_storage.delete(str(file_path))
            raise

    def list_documents(self, user_id: str) -> list[Document]:
        return self._documents.list(user_id)

    def get_document(self, document_id: str, user_id: str) -> Document | None:
        return self._documents.get(document_id, user_id)

    def delete_document(self, document_id: str, user_id: str) -> None:
        document = self._documents.get(document_id, user_id)
        self._documents.delete(document_id, user_id)
        self._retriever.remove_document(document_id)
        if document is not None:
            self._file_storage.delete(document.file_path)

    def reindex_document(self, document_id: str, user_id: str) -> Document | None:
        document = self._documents.get(document_id, user_id)
        if document is None:
            return None

        text = self._extractor.extract(Path(document.file_path), document.content_type)
        refreshed = Document(
            id=document.id,
            filename=document.filename,
            text=text,
            content_type=document.content_type,
            file_path=document.file_path,
            size_bytes=document.size_bytes,
            user_id=document.user_id,
            status="indexed",
            created_at=document.created_at,
        )
        chunks = self._text_chunker.chunk(refreshed)
        indexed = Document(
            id=refreshed.id,
            filename=refreshed.filename,
            text=refreshed.text,
            content_type=refreshed.content_type,
            file_path=refreshed.file_path,
            size_bytes=refreshed.size_bytes,
            user_id=refreshed.user_id,
            chunk_count=len(chunks),
            status="indexed",
            created_at=refreshed.created_at,
        )
        self._retriever.remove_document(document_id)
        self._retriever.index(indexed, chunks)
        self._documents.add(indexed)
        return indexed

    def answer_question(
        self,
        user_id: str,
        question: str,
        limit: int = 4,
        session_id: str | None = None,
    ) -> RagAnswer:
        session_id = session_id or "default"
        self._conversations.get_or_create(session_id, user_id, title=_title_from_question(question))
        history = self._conversations.list_messages(session_id, user_id, limit=8)
        chunks = self._retriever.search(question, user_id=user_id, limit=limit)
        generator = (
            self._answer_generator.get_generator_for_user(user_id)
            if isinstance(self._answer_generator, AnswerGeneratorFactory)
            else self._answer_generator
        )
        response = generator.generate(question, chunks, history=history)
        citations = [
            Citation(
                document_id=chunk.document_id,
                filename=chunk.filename,
                chunk_id=chunk.id,
                text=chunk.text,
                score=chunk.score,
                metadata=chunk.metadata,
            )
            for chunk in chunks
        ]
        self._conversations.append_message(
            session_id,
            user_id,
            role="user",
            content=question,
            title=_title_from_question(question),
        )
        self._conversations.append_message(
            session_id,
            user_id,
            role="assistant",
            content=response.answer,
            structured=_structured_payload(response),
        )
        return RagAnswer(response=response, citations=citations)

    def search_chunks(self, user_id: str, query: str, limit: int = 4) -> list[Citation]:
        chunks = self._retriever.search(query, user_id=user_id, limit=limit)
        return [
            Citation(
                document_id=chunk.document_id,
                filename=chunk.filename,
                chunk_id=chunk.id,
                text=chunk.text,
                score=chunk.score,
                metadata=chunk.metadata,
            )
            for chunk in chunks
        ]

    def rename_conversation(self, user_id: str, session_id: str, title: str) -> str:
        session = self._conversations.rename(session_id, user_id, title)
        return session.title

    def list_conversations(self, user_id: str):
        return self._conversations.list_sessions(user_id)

    def delete_conversation(self, user_id: str, session_id: str) -> None:
        self._conversations.delete(session_id, user_id)


def _structured_payload(response: StructuredRagResponse) -> dict:
    return {
        "answer": response.answer,
        "summary": response.summary,
        "key_points": list(response.key_points),
        "sources": [
            {"document": source.document, "page": source.page}
            for source in response.sources
        ],
        "confidence": response.confidence,
        "follow_up_questions": list(response.follow_up_questions),
    }


def _title_from_question(question: str) -> str:
    clean = " ".join(question.split())
    return clean[:48] if len(clean) <= 48 else f"{clean[:45]}..."
