"""The corpus embedding model and the embedder that calls it (MKC-49.3, ADR 004, decision 71).

`EMBEDDING` is the one place that names the model and its dimension; migration 0013 bakes
the dimension into `chunk.embedding`, so changing either means a new migration and a reload.
The price lives in `mkc/models/models.yaml`. Every call goes through
`mkc.models.client.EmbeddingClient` (AGENTS.md model rules); this module imports no
provider package, so `mkc.db.models` can read `EMBEDDING.dim` cheaply.

Qwen3-Embedding wants an instruction on queries and none on documents, so corpus chunks are
embedded exactly as stored; the query side (MKC-50) adds the instruction.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from mkc.models.types import Provider

if TYPE_CHECKING:
    from mkc.config import Settings
    from mkc.models.client import EmbeddingClient


@dataclass(frozen=True)
class EmbeddingModel:
    provider: Provider
    model: str
    dim: int


EMBEDDING = EmbeddingModel(provider="openrouter", model="qwen/qwen3-embedding-8b", dim=1024)
"""Qwen3-Embedding-8B through OpenRouter (zero data retention), cut to 1024 dimensions."""


class Embedder(Protocol):
    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


class ProviderEmbedder:
    """An `Embedder` over `EmbeddingClient`; it adds up tokens and cost for the caller."""

    def __init__(self, client: "EmbeddingClient", *, dim: int = EMBEDDING.dim) -> None:
        self.client = client
        self.dim = dim
        self.model = EMBEDDING.model
        self.input_tokens = 0
        self.cost_eur = 0.0

    @classmethod
    def from_settings(cls, settings: "Settings") -> "ProviderEmbedder":
        from mkc.models.client import EmbeddingClient

        client = EmbeddingClient.from_settings(
            settings, provider=EMBEDDING.provider, model=EMBEDDING.model, dim=EMBEDDING.dim
        )
        return cls(client)

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        reply = self.client.embed(texts)
        self.input_tokens += reply.input_tokens
        self.cost_eur += reply.cost_eur
        return reply.vectors
