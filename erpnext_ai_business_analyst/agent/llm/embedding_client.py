"""
Provider-agnostic embedding interface — separate from LLMClient since
embeddings are a different capability (a vector, not generated text). Same
principle as LLMClient: the retrieval layer (agent/retrieval.py) depends
only on this interface, never on a specific provider's embedding API.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class EmbeddingClient(ABC):
    @abstractmethod
    def embed(self, text: str) -> list[float]:
        """Return the embedding vector for the given text."""
        raise NotImplementedError