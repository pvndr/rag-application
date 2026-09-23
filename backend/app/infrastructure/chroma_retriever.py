from pathlib import Path
from typing import Any, cast

from app.domain.entities import Chunk, Document
from app.domain.repositories import Retriever
from app.infrastructure.embedding_provider import SentenceTransformerEmbeddingProvider


class ChromaRetriever(Retriever):
    def __init__(
        self,
        persist_path: str,
        collection_name: str,
        embedding_provider: SentenceTransformerEmbeddingProvider,
    ) -> None:
        import chromadb

        self._embedding_provider = embedding_provider
        resolved_path = Path(persist_path).resolve()
        resolved_path.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(resolved_path))
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def index(self, document: Document, chunks: list[Chunk]) -> None:
        if not chunks:
            return

        texts = [chunk.text for chunk in chunks]
        embeddings = self._embedding_provider.embed_documents(texts)
        self._collection.add(
            ids=[chunk.id for chunk in chunks],
            documents=texts,
            embeddings=cast(Any, embeddings),
            metadatas=cast(Any, [chunk.metadata for chunk in chunks]),
        )

    def remove_document(self, document_id: str) -> None:
        self._collection.delete(where={"document_id": document_id})

    def search(self, query: str, user_id: str, limit: int = 4) -> list[Chunk]:
        embedding = self._embedding_provider.embed_query(query)
        # Query by precomputed embedding so Chroma can use its persistent HNSW
        # cosine index directly. Only payload fields required by the API are
        # requested to keep retrieval lightweight.
        result = self._collection.query(
            query_embeddings=[embedding],
            n_results=limit,
            where={"user_id": user_id},
            include=["documents", "metadatas", "distances"],
        )
        raw_documents = result.get("documents")
        documents = raw_documents[0] if raw_documents else []

        raw_metadatas = result.get("metadatas")
        metadatas = raw_metadatas[0] if raw_metadatas else []

        raw_ids = result.get("ids")
        ids = raw_ids[0] if raw_ids else []

        raw_distances = result.get("distances")
        distances = raw_distances[0] if raw_distances else []

        chunks: list[Chunk] = []
        for chunk_id, text, metadata, distance in zip(ids, documents, metadatas, distances):
            score = max(0.0, 1.0 - float(distance))
            clean_metadata: dict[str, str | int | float] = (
                {k: v for k, v in metadata.items() if isinstance(v, (str, int, float))}
                if isinstance(metadata, dict)
                else {}
            )
            chunks.append(
                Chunk(
                    id=chunk_id,
                    document_id=str(clean_metadata.get("document_id", "")),
                    filename=str(clean_metadata.get("filename", "")),
                    text=text,
                    metadata=clean_metadata,
                    score=round(score, 4),
                )
            )
        return chunks
