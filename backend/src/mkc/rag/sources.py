"""The corpus sources file: what the narrow corpus holds and under which licence (MKC-49.1).

`backend/data/corpus_sources.yaml` lists each source's id, title, type, URL, version and
licence class, and never its text: the loader fetches the text at run time (AGENTS.md data
rules). Laws and BNetzA decisions are official works (§ 5 UrhG) and `official`; operator
texts are someone else's and `restricted`, so they never land in the repo.
"""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

DEFAULT_SOURCES_PATH = Path(__file__).resolve().parents[3] / "data" / "corpus_sources.yaml"
"""`backend/data/corpus_sources.yaml` next to the source tree. The image installs `mkc` into
the venv, where this path does not exist; it ships the file at `IMAGE_SOURCES_PATH`."""

IMAGE_SOURCES_PATH = Path("/app/data/corpus_sources.yaml")
"""Where the backend image ships the sources file (`backend/Dockerfile`)."""


class CorpusSourceError(ValueError):
    """The sources file is missing, malformed or breaks a rule."""


class LicenceClass(StrEnum):
    OFFICIAL = "official"
    """Laws and BNetzA decisions: official works, free to use and store."""
    RESTRICTED = "restricted"
    """Operator texts: never written inside the repo."""


class SourceType(StrEnum):
    LAW = "law"
    BNETZA_DECISION = "bnetza_decision"
    OPERATOR_TEXT = "operator_text"


OFFICIAL_TYPES = frozenset({SourceType.LAW, SourceType.BNETZA_DECISION})


@dataclass(frozen=True)
class CorpusSource:
    id: str
    title: str
    source_type: SourceType
    url: str
    version: str
    licence: LicenceClass


class _Entry(BaseModel):
    """One entry as written in the file. `extra="forbid"` keeps any text field out."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    title: str = Field(min_length=1)
    source_type: SourceType
    url: str = Field(pattern=r"^https://[^\s/]+/\S*$")
    version: str = Field(min_length=1)
    licence: LicenceClass

    @field_validator("version", mode="before")
    @classmethod
    def _version_as_text(cls, value: Any) -> Any:
        return str(value) if isinstance(value, int | float) else value


def _licence_for(source_type: SourceType) -> LicenceClass:
    return LicenceClass.OFFICIAL if source_type in OFFICIAL_TYPES else LicenceClass.RESTRICTED


def sources_path() -> Path:
    """`MKC_CORPUS_SOURCES_FILE` if set, else the source-tree file, else the image's file."""
    from mkc.config import get_settings

    configured = get_settings().corpus_sources_file
    if configured:
        return Path(configured)
    return DEFAULT_SOURCES_PATH if DEFAULT_SOURCES_PATH.is_file() else IMAGE_SOURCES_PATH


def load_sources(path: Path | None = None) -> list[CorpusSource]:
    """Read and check the sources file (default: `sources_path()`); every problem is a
    `CorpusSourceError`."""
    path = sources_path() if path is None else path
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise CorpusSourceError(f"sources file not readable: {path}: {error}") from error
    except yaml.YAMLError as error:
        raise CorpusSourceError(f"sources file is not valid YAML: {path}: {error}") from error
    entries = data.get("sources") if isinstance(data, dict) else None
    if not isinstance(entries, list) or not entries:
        raise CorpusSourceError(f"{path}: needs a non-empty `sources:` list")
    sources: list[CorpusSource] = []
    for number, raw in enumerate(entries, start=1):
        try:
            entry = _Entry.model_validate(raw)
        except ValidationError as error:
            raise CorpusSourceError(f"{path}: source {number} is invalid: {error}") from error
        if entry.licence is not _licence_for(entry.source_type):
            raise CorpusSourceError(
                f"{path}: source {entry.id!r}: a {entry.source_type.value} is "
                f"{_licence_for(entry.source_type).value}, not {entry.licence.value}"
            )
        sources.append(CorpusSource(**entry.model_dump()))
    ids = [s.id for s in sources]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        raise CorpusSourceError(f"{path}: duplicate source ids {duplicates}")
    return sources
