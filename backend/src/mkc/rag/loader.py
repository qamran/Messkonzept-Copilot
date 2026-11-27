"""Load the corpus: fetch, chunk, embed and store each source (MKC-49.5, features 69, 70).

`load_corpus` works inside the caller's transaction and only flushes. Re-loading a source
replaces its document row and chunks (keyed by `source_id`), so there are never two copies.

Licence guard: a non-official (`restricted`) text must never land inside the repo. When a
cache folder is given and it lies inside the repo while any source is restricted, the whole
load is refused before anything is fetched or written (AGENTS.md data rules).
"""

import hashlib
from collections.abc import Callable, Sequence
from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.orm import Session

from mkc.db.models import Chunk as ChunkRow
from mkc.db.models import CorpusDocument
from mkc.rag.chunking import Layout, chunk_text
from mkc.rag.embeddings import Embedder
from mkc.rag.sources import CorpusSource, LicenceClass, SourceType

REPO_ROOT = Path(__file__).resolve().parents[4]
"""The repository root (`backend/src/mkc/rag/loader.py` → four levels up)."""

Fetcher = Callable[[CorpusSource], str]
"""Returns a source's plain text."""


class CorpusLicenceError(ValueError):
    """A restricted text would be written inside the repo."""


class CorpusLoadError(RuntimeError):
    """A source gave no text, or the embedder's reply does not fit the chunks."""


def check_cache_dir(
    cache_dir: Path, sources: Sequence[CorpusSource], *, repo_root: Path = REPO_ROOT
) -> None:
    """Refuse a cache inside the repo when any source is restricted (paths resolved)."""
    restricted = [s.id for s in sources if s.licence is LicenceClass.RESTRICTED]
    if restricted and cache_dir.resolve().is_relative_to(repo_root.resolve()):
        raise CorpusLicenceError(
            f"cache {cache_dir} is inside the repo {repo_root}; restricted sources "
            f"{restricted} must never be written there. Use a folder outside the repo."
        )


def layout_for(source: CorpusSource) -> Layout:
    return "law" if source.source_type is SourceType.LAW else "sections"


def _cache_file(cache_dir: Path, source: CorpusSource) -> Path:
    version = hashlib.sha256(f"{source.url}\n{source.version}".encode()).hexdigest()[:12]
    return cache_dir / f"{source.id}-{version}.txt"


def _text(source: CorpusSource, fetcher: Fetcher, cache_dir: Path | None) -> str:
    """The source's text: from the cache when this URL and version are there, else fetched."""
    if cache_dir is None:
        return fetcher(source)
    path = _cache_file(cache_dir, source)
    if path.is_file():
        return path.read_text(encoding="utf-8")
    body = fetcher(source)
    cache_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return body


def load_corpus(
    session: Session,
    sources: Sequence[CorpusSource],
    *,
    embedder: Embedder,
    fetcher: Fetcher,
    cache_dir: Path | None = None,
    repo_root: Path = REPO_ROOT,
) -> dict[str, int]:
    """Load every source; returns the number of chunks per source id."""
    if cache_dir is not None:
        check_cache_dir(cache_dir, sources, repo_root=repo_root)
    report: dict[str, int] = {}
    for source in sources:
        chunks = chunk_text(
            _text(source, fetcher, cache_dir), source_id=source.id, layout=layout_for(source)
        )
        if not chunks:
            raise CorpusLoadError(f"source {source.id!r} gave no text to chunk")
        vectors = embedder.embed([c.text for c in chunks])
        if len(vectors) != len(chunks):
            raise CorpusLoadError(
                f"source {source.id!r}: {len(vectors)} vectors for {len(chunks)} chunks"
            )
        session.execute(delete(CorpusDocument).where(CorpusDocument.source_id == source.id))
        document = CorpusDocument(
            source_id=source.id,
            title=source.title,
            source_type=source.source_type.value,
            url=source.url,
            version=source.version,
            licence=source.licence.value,
        )
        session.add(document)
        session.flush()
        session.add_all(
            ChunkRow(
                document_id=document.id,
                ordinal=chunk.ordinal,
                source_ref=chunk.source_ref,
                text=chunk.text,
                embedding=vector,
            )
            for chunk, vector in zip(chunks, vectors, strict=True)
        )
        session.flush()
        report[source.id] = len(chunks)
    return report
