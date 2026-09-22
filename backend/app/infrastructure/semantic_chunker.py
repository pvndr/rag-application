import re

from app.domain.entities import Chunk, Document
from app.domain.repositories import TextChunker

SENTENCE_PATTERN = re.compile(r"(?<=[.!?])\s+")


class SemanticTextChunker(TextChunker):
    def __init__(self, chunk_size: int, chunk_overlap: int) -> None:
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap

    def chunk(self, document: Document) -> list[Chunk]:
        paragraphs = [part.strip() for part in re.split(r"\n{2,}", document.text)]
        units = [
            sentence.strip()
            for paragraph in paragraphs
            for sentence in SENTENCE_PATTERN.split(paragraph)
            if sentence.strip()
        ]
        if not units:
            units = [document.text]

        chunks: list[str] = []
        current = ""
        for unit in units:
            if len(unit) > self._chunk_size:
                chunks.extend(self._split_long_text(unit))
                continue
            candidate = f"{current} {unit}".strip()
            if current and len(candidate) > self._chunk_size:
                chunks.append(current)
                current = self._with_overlap(current, unit)
            else:
                current = candidate

        if current:
            chunks.append(current)

        return [
            Chunk(
                id=f"{document.id}:{index}",
                document_id=document.id,
                filename=document.filename,
                text=text,
                metadata={
                    "document_id": document.id,
                    "user_id": document.user_id,
                    "filename": document.filename,
                    "chunk_index": index,
                    "content_type": document.content_type,
                    "source_path": document.file_path,
                },
            )
            for index, text in enumerate(chunks)
            if text.strip()
        ]

    def _split_long_text(self, text: str) -> list[str]:
        chunks: list[str] = []
        step = self._chunk_size - self._chunk_overlap
        start = 0
        while start < len(text):
            chunks.append(text[start : start + self._chunk_size])
            start += step
        return chunks

    def _with_overlap(self, previous: str, next_unit: str) -> str:
        overlap = previous[-self._chunk_overlap :].strip()
        return f"{overlap} {next_unit}".strip()
