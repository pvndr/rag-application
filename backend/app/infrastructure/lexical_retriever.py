import math
import re
from collections import Counter

from app.domain.entities import Chunk, Document
from app.domain.repositories import Retriever

TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9]+")


class LexicalRetriever(Retriever):
    def __init__(self, chunk_size: int, chunk_overlap: int) -> None:
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        self._chunks: dict[str, Chunk] = {}
        self._vectors: dict[str, Counter[str]] = {}

    def index(self, document: Document, chunks: list[Chunk]) -> None:
        for chunk in chunks:
            self._chunks[chunk.id] = chunk
            self._vectors[chunk.id] = Counter(_tokenize(chunk.text))

    def remove_document(self, document_id: str) -> None:
        chunk_ids = [
            chunk_id
            for chunk_id, chunk in self._chunks.items()
            if chunk.document_id == document_id
        ]
        for chunk_id in chunk_ids:
            self._chunks.pop(chunk_id, None)
            self._vectors.pop(chunk_id, None)

    def search(self, query: str, limit: int = 4) -> list[Chunk]:
        query_vector = Counter(_tokenize(query))
        if not query_vector:
            return []

        scored: list[Chunk] = []
        for chunk_id, vector in self._vectors.items():
            score = _cosine_similarity(query_vector, vector)
            if score > 0:
                chunk = self._chunks[chunk_id]
                scored.append(
                    Chunk(
                        id=chunk.id,
                        document_id=chunk.document_id,
                        filename=chunk.filename,
                        text=chunk.text,
                        score=round(score, 4),
                    )
                )

        return sorted(scored, key=lambda chunk: chunk.score, reverse=True)[:limit]

    def _split_text(self, text: str) -> list[str]:
        clean_text = " ".join(text.split())
        if not clean_text:
            return []

        chunks: list[str] = []
        start = 0
        step = max(1, self._chunk_size - self._chunk_overlap)

        while start < len(clean_text):
            end = min(len(clean_text), start + self._chunk_size)
            chunks.append(clean_text[start:end])
            if end == len(clean_text):
                break
            start += step

        return chunks


def _tokenize(text: str) -> list[str]:
    return TOKEN_PATTERN.findall(text.lower())


def _cosine_similarity(left: Counter[str], right: Counter[str]) -> float:
    shared_tokens = set(left) & set(right)
    dot_product = sum(left[token] * right[token] for token in shared_tokens)
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))

    if left_norm == 0 or right_norm == 0:
        return 0.0

    return dot_product / (left_norm * right_norm)
