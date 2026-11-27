"""LBS reference data: the BDEW Codeliste der Lokationsbündelstrukturen as cited facts.

The data file holds only codes, Bezeichnung, page and object composition, plus a source
block naming the edition (docs/261120261404-codeliste-research.md, decision 50). It is
built by scripts/build_lbs_yaml.py; this module validates and loads it.

Check digit: the Codeliste defines none. Every code fits BDEW's Lok- und
Waggon-Kennzeichnungsverfahren (AWH "Identifikatoren in der Marktkommunikation" 1.2,
section 8.1), so the loader rejects codes that fail it. That catches typos; it does not
prove a code is in the Codeliste.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

DEFAULT_PATH = Path(__file__).resolve().parents[3] / "data" / "lbs_structures.yaml"

OBJEKTE = ("MeLo", "MaLo", "TR", "NeLo")
# The MeLo's function (Funktion der Messlokation); other objects have none.
FUNKTIONEN = ("Netzübergabe", "Hinterschaltung", "Differenzmessung")
FLEXIBILITAET = ("Starr", "Flexibel")


class LbsDataError(ValueError):
    """The LBS data file is malformed or breaks a rule."""


@dataclass(frozen=True)
class LbsObject:
    """One position (object code) in a Lokationsbündelstruktur.

    `richtung` is None where the Codeliste has "--" (the NeLo). `referenz_melo` and
    `referenz_nelo` are the object codes a flexible object refers to (empty if none).
    """

    code: str
    objekt: str
    funktion: str | None
    richtung: str | None
    ebene: int
    flexibilitaet: str
    anzahl: str
    referenz_melo: tuple[str, ...]
    referenz_nelo: tuple[str, ...]


@dataclass(frozen=True)
class LbsStructure:
    """One Lokationsbündelstruktur: its code, Bezeichnung, page in the source and objects."""

    code: str
    bezeichnung: str
    page: int
    objects: tuple[LbsObject, ...]


@dataclass(frozen=True)
class LbsSource:
    """The edition of the Codeliste the data comes from."""

    title: str
    publisher: str
    version: str
    edition: str
    applies_from: str
    url: str
    sha256: str
    retrieved: str


def check_digit(payload: str) -> int:
    """Lok- und Waggon-Kennzeichnungsverfahren: odd positions (from the left, starting at 1)
    count once, even positions twice; the check digit tops the sum up to a multiple of 10."""
    if not (payload.isascii() and payload.isdigit()):
        raise ValueError(f"not ASCII digits: {payload!r}")
    odd = sum(int(d) for d in payload[0::2])
    even = sum(int(d) for d in payload[1::2])
    return (10 - (odd + 2 * even) % 10) % 10


def is_valid_code(code: str) -> bool:
    """13 ASCII digits, and the last one is the check digit of the first 12. Other Unicode
    digits (`²`, full-width, Arabic-Indic) are no code: False, never an exception."""
    if len(code) != 13 or not (code.isascii() and code.isdigit()):
        return False
    return check_digit(code[:12]) == int(code[12])


def _read(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise LbsDataError(f"{path}: top level must be a mapping")
    return data


def _string(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value:
        raise LbsDataError(f"{where}: must be a non-empty string, got {value!r}")
    return value


def _int(value: Any, where: str) -> int:
    # bool is an int in Python; YAML `yes` must not pass as 1.
    if not isinstance(value, int) or isinstance(value, bool):
        raise LbsDataError(f"{where}: must be an integer, got {value!r}")
    return value


def _code(value: Any, where: str) -> str:
    code = _string(value, where)
    if not is_valid_code(code):
        raise LbsDataError(f"{where}: {code} is not 13 digits with a valid check digit")
    return code


def _choice(value: Any, allowed: tuple[str, ...], where: str) -> str:
    text = _string(value, where)
    if text not in allowed:
        raise LbsDataError(f"{where}: {text!r} is not one of {allowed}")
    return text


def _codes(value: Any, where: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise LbsDataError(f"{where}: must be a list of codes, got {value!r}")
    return tuple(_code(v, f"{where}[{i}]") for i, v in enumerate(value))


def _object(raw: Any, where: str) -> LbsObject:
    if not isinstance(raw, dict):
        raise LbsDataError(f"{where}: must be a mapping")
    funktion = raw.get("funktion")
    richtung = raw.get("richtung")
    return LbsObject(
        code=_code(raw.get("code"), f"{where}.code"),
        objekt=_choice(raw.get("objekt"), OBJEKTE, f"{where}.objekt"),
        funktion=None if funktion is None else _choice(funktion, FUNKTIONEN, f"{where}.funktion"),
        richtung=None if richtung is None else _string(richtung, f"{where}.richtung"),
        ebene=_int(raw.get("ebene"), f"{where}.ebene"),
        flexibilitaet=_choice(raw.get("flexibilitaet"), FLEXIBILITAET, f"{where}.flexibilitaet"),
        anzahl=_string(raw.get("anzahl"), f"{where}.anzahl"),
        referenz_melo=_codes(raw.get("referenz_melo"), f"{where}.referenz_melo"),
        referenz_nelo=_codes(raw.get("referenz_nelo"), f"{where}.referenz_nelo"),
    )


def _structure(raw: Any, where: str) -> LbsStructure:
    if not isinstance(raw, dict):
        raise LbsDataError(f"{where}: must be a mapping")
    code = _code(raw.get("code"), f"{where}.code")
    objects = raw.get("objects")
    if not isinstance(objects, list) or not objects:
        raise LbsDataError(f"{where} ({code}): objects must be a non-empty list")
    parsed = tuple(_object(o, f"{where}.objects[{i}]") for i, o in enumerate(objects))
    present = {o.code for o in parsed}
    for obj in parsed:
        for ref in (*obj.referenz_melo, *obj.referenz_nelo):
            if ref not in present:
                raise LbsDataError(f"{code}: {obj.code} refers to {ref}, not in this structure")
    return LbsStructure(
        code=code,
        bezeichnung=_string(raw.get("bezeichnung"), f"{where}.bezeichnung"),
        page=_int(raw.get("page"), f"{where}.page"),
        objects=parsed,
    )


def load_lbs(path: Path = DEFAULT_PATH) -> list[LbsStructure]:
    """Load and validate the structures; raises LbsDataError on any broken rule."""
    raw = _read(path).get("structures")
    if not isinstance(raw, list) or not raw:
        raise LbsDataError(f"{path}: structures must be a non-empty list")
    structures = [_structure(s, f"structures[{i}]") for i, s in enumerate(raw)]
    seen: set[str] = set()
    for structure in structures:
        if structure.code in seen:
            raise LbsDataError(f"duplicate structure code {structure.code}")
        seen.add(structure.code)
    return structures


def load_lbs_source(path: Path = DEFAULT_PATH) -> LbsSource:
    """Load the source block that names the Codeliste edition."""
    raw = _read(path).get("source")
    if not isinstance(raw, dict):
        raise LbsDataError(f"{path}: source must be a mapping")
    fields = LbsSource.__dataclass_fields__
    return LbsSource(**{name: _string(raw.get(name), f"source.{name}") for name in fields})
