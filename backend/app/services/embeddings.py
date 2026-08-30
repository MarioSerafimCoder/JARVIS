from __future__ import annotations

from abc import ABC, abstractmethod
from math import sqrt


class EmbeddingProvider(ABC):
    name = "base"
    model_name = "unknown"

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]: ...

    def health(self) -> dict:
        try:
            vector = self.embed(["teste local"])[0]
            return {"status": "available", "provider": self.name, "model": self.model_name, "dimensions": len(vector)}
        except Exception as exc:
            return {"status": "fallback_fts5", "provider": self.name, "model": self.model_name, "error": str(exc)}


class LocalSentenceTransformerProvider(EmbeddingProvider):
    """Loads a multilingual model from the local cache only; it never downloads at runtime."""

    name = "sentence_transformers_local"
    model_name = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

    def __init__(self) -> None:
        self._model = None

    def _load(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise RuntimeError("sentence-transformers não está instalado; usando FTS5.") from exc
            self._model = SentenceTransformer(self.model_name, local_files_only=True, device="cpu")
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = self._load().encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return [vector.tolist() for vector in vectors]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    denominator = sqrt(sum(value * value for value in left)) * sqrt(sum(value * value for value in right))
    if not denominator:
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=True)) / denominator


embedding_provider: EmbeddingProvider = LocalSentenceTransformerProvider()
