"""The operator allow-list: `backend/data/operators.yaml` (MKC-21.1, decision 63).

`MKC_OPERATORS_FILE` names the file; empty means the copy next to the source tree. The image
installs `mkc` into the venv, so its Dockerfile copies the YAML and sets the variable.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml

from mkc.config import get_settings

DEFAULT_PATH = Path(__file__).resolve().parents[3] / "data" / "operators.yaml"
FIELDS = ("id", "name", "voltage_level", "url", "allowed_hosts")


class OperatorsFileError(ValueError):
    """The operators file is malformed or breaks a rule."""


@dataclass(frozen=True)
class OperatorConfig:
    id: str
    name: str
    voltage_level: str
    url: str
    allowed_hosts: tuple[str, ...]


def operators_path() -> Path:
    return Path(get_settings().operators_file or DEFAULT_PATH)


def load_operators(path: Path | None = None) -> dict[str, OperatorConfig]:
    """Every operator of the file by id. Hosts are kept in lower case; each operator's URL
    must be https and on its own `allowed_hosts`."""
    path = path or operators_path()
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    entries = data.get("operators") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        raise OperatorsFileError(f"{path}: needs a top-level 'operators' list")
    ops: dict[str, OperatorConfig] = {}
    for entry in entries:
        op = _operator(entry)
        if op.id in ops:
            raise OperatorsFileError(f"{path}: operator {op.id!r} listed twice")
        ops[op.id] = op
    return ops


def _operator(entry: Any) -> OperatorConfig:
    if not isinstance(entry, dict):
        raise OperatorsFileError(f"an operator must be a mapping, not {entry!r}")
    ident = entry.get("id")
    missing = [key for key in FIELDS if not entry.get(key)]
    if missing:
        raise OperatorsFileError(f"operator {ident!r}: missing {', '.join(missing)}")
    hosts = tuple(str(h).lower() for h in entry["allowed_hosts"])
    url = str(entry["url"])
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.username is not None or parts.password is not None:
        raise OperatorsFileError(f"operator {ident!r}: the url must be https, without userinfo")
    if parts.hostname not in hosts:
        raise OperatorsFileError(f"operator {ident!r}: the url's host is not on allowed_hosts")
    return OperatorConfig(
        id=str(ident),
        name=str(entry["name"]),
        voltage_level=str(entry["voltage_level"]),
        url=url,
        allowed_hosts=hosts,
    )
