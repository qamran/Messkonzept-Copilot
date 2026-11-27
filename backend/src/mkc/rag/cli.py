"""`mkc corpus load` (MKC-49.6, features 69 and 70): fetch, chunk, embed and index the
sources of a sources file in one transaction.

Exit codes: 0 loaded; 1 a fetch, the embedder or the database failed (nothing is written);
2 bad input (sources file, `--source` id, a cache folder inside the repo, for any source).

The embedder calls the provider, so it needs `MKC_MODEL_MODE=live` and
`MKC_OPENROUTER_API_KEY`. Tests replace `make_embedder` and `make_fetcher`.
"""

from pathlib import Path
from typing import Annotated

import typer
from sqlalchemy.orm import sessionmaker

from mkc.config import Settings, get_settings
from mkc.db.session import get_engine
from mkc.models.types import ModelError
from mkc.rag.embeddings import Embedder, ProviderEmbedder
from mkc.rag.fetch import CorpusFetchError, http_fetcher
from mkc.rag.loader import CorpusLicenceError, CorpusLoadError, Fetcher, load_corpus
from mkc.rag.sources import DEFAULT_SOURCES_PATH, CorpusSourceError, load_sources

corpus_app = typer.Typer(no_args_is_help=True, help="Load the RAG corpus (MKC-49).")

SourcesOpt = Annotated[Path, typer.Option("--sources", help="The sources file (YAML).")]
OnlyOpt = Annotated[
    list[str] | None, typer.Option("--source", help="Load only this source id (repeatable).")
]
CacheOpt = Annotated[
    Path | None,
    typer.Option("--cache-dir", help="Keep fetched texts here; must be outside the repo."),
]


def make_embedder(settings: Settings) -> Embedder:
    """The corpus embedder (tests replace it with a fake)."""
    return ProviderEmbedder.from_settings(settings)


def make_fetcher(settings: Settings) -> Fetcher:
    """The HTTP fetcher (tests replace it with a fake)."""
    return http_fetcher()


def _fail(message: str, code: int) -> typer.Exit:
    typer.echo(message, err=True)
    return typer.Exit(code)


@corpus_app.command()
def load(
    sources: SourcesOpt = DEFAULT_SOURCES_PATH,
    source: OnlyOpt = None,
    cache_dir: CacheOpt = None,
) -> None:
    """Fetch, chunk, embed and index every source of the file (or the chosen ones)."""
    try:
        chosen = load_sources(sources)
    except CorpusSourceError as error:
        raise _fail(str(error), 2) from error
    if source:
        unknown = sorted(set(source) - {s.id for s in chosen})
        if unknown:
            raise _fail(f"no source {unknown} in {sources}", 2)
        chosen = [s for s in chosen if s.id in source]
    settings = get_settings()
    try:
        embedder = make_embedder(settings)
        with sessionmaker(bind=get_engine()).begin() as session:
            report = load_corpus(
                session, chosen, embedder=embedder, fetcher=make_fetcher(settings),
                cache_dir=cache_dir,
            )  # fmt: skip
    except CorpusLicenceError as error:
        raise _fail(str(error), 2) from error
    except (CorpusFetchError, CorpusLoadError, ModelError) as error:
        raise _fail(f"corpus not loaded, nothing written: {error}", 1) from error
    for source_id, chunks in report.items():
        typer.echo(f"{source_id}: {chunks} chunks")
    if isinstance(embedder, ProviderEmbedder):
        typer.echo(f"embeddings: {embedder.input_tokens} tokens, {embedder.cost_eur:.6f} EUR")
