from typing import Any

from app.application.errors import EmbeddingModelError


class SentenceTransformerEmbeddingProvider:
    def __init__(self, model_name: str, cache_folder: str | None = None) -> None:
        self._model_name = model_name
        self._cache_folder = cache_folder or None
        self._model: Any | None = None

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return self._load_model().encode(texts, normalize_embeddings=True).tolist()

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]

    def _load_model(self) -> Any:
        if self._model is not None:
            return self._model

        from sentence_transformers import SentenceTransformer

        try:
            self._model = SentenceTransformer(
                self._model_name,
                cache_folder=self._cache_folder,
                local_files_only=True,
            )
        except Exception:
            try:
                self._model = SentenceTransformer(
                    self._model_name,
                    cache_folder=self._cache_folder,
                    local_files_only=False,
                )
            except Exception as exc:
                raise EmbeddingModelError(
                    "Embedding model is unavailable. Download or cache "
                    "sentence-transformers/all-MiniLM-L6-v2 and retry."
                ) from exc

        return self._model
