"""`mkc gold split|draft|export|import` (MKC-24, feature 33, design 11.1).

- `split` writes the dev/test split file from a YAML list of concept keys.
- `draft` fetches an operator's public catalogue into memory (never to disk), segments it,
  and drafts the chosen concepts with the `gold_draft` role; each call's cost is printed.
- `export` writes gold items as JSON for the user to verify; `--blind` writes empty blind
  items for the given keys, with no draft in them.
- `import` reads that file back; `--verified-by` names the person who verified it.

Exit codes: 0 done, 1 refused (a data rule, a spend cap), 2 bad input.
"""

import hashlib
import io
import json
from pathlib import Path
from typing import Annotated, Any, Literal

import pdfplumber
import typer
import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from mkc.config import Settings, get_settings
from mkc.db.models import GoldItem
from mkc.db.session import get_engine
from mkc.extraction.fetch import http_get
from mkc.extraction.operators import load_operators
from mkc.extraction.render import render_region
from mkc.extraction.segment import SEGMENTERS, ConceptRegion
from mkc.gold.draft import draft_concept, ensure_independent
from mkc.gold.exchange import GoldFileError, export_items, import_items
from mkc.gold.facts import FactsOnlyError
from mkc.gold.split import GOLD_SPLIT_FILE, concept_key, dump_split, load_split, split_keys
from mkc.gold.store import VerifiedItem, store_gold_draft
from mkc.models.client import ModelClient
from mkc.models.config import DEFAULT_MODELS_FILE, ModelsConfig, load_models_config
from mkc.models.types import Image, ModelError

gold_app = typer.Typer(no_args_is_help=True, help="Gold data: split, draft, export, import.")

Side = Literal["dev", "test"]


def _fail(message: str, code: int) -> typer.Exit:
    typer.echo(message, err=True)
    return typer.Exit(code)


def _sessions() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine())


@gold_app.command()
def split(
    keys: Annotated[Path, typer.Option("--keys", help="YAML list of concept keys.")],
    out: Annotated[Path, typer.Option("--out", help="The split file.")] = GOLD_SPLIT_FILE,
    pin_dev: Annotated[
        list[str] | None, typer.Option("--pin-dev", help="A key that must be in dev.")
    ] = None,
) -> None:
    """Write the dev/test split of --keys (about 50/50 per operator) to --out."""
    try:
        listed = yaml.safe_load(keys.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise _fail(f"keys file {keys}: {error}", 2) from error
    if not isinstance(listed, list) or not all(isinstance(k, str) for k in listed):
        raise _fail(f"keys file {keys}: needs a YAML list of keys (strings)", 2)
    try:
        text = dump_split(split_keys(listed, pinned_dev=pin_dev or []))
    except ValueError as error:
        raise _fail(str(error), 2) from error
    out.write_bytes(text.encode("utf-8"))  # LF on every platform
    typer.echo(f"{out}: {len(set(listed))} keys")


# --- draft ------------------------------------------------------------------------------


def models_config(settings: Settings) -> ModelsConfig:
    """The models file the client uses (`MKC_MODELS_FILE`, else the package's)."""
    return load_models_config(
        Path(settings.models_file) if settings.models_file else DEFAULT_MODELS_FILE
    )


def make_client(settings: Settings) -> ModelClient:
    """The model client of `gold draft` (tests replace it with a fake)."""
    return ModelClient.from_settings(settings)


def fetch_catalogue(operator_id: str) -> bytes:
    """The operator's public PDF, fetched into memory from its allow-listed URL; it is never
    written to disk (tests replace this with a synthetic PDF)."""
    operator = load_operators()[operator_id]
    content = http_get(operator.url, allowed_hosts=operator.allowed_hosts).content
    if not content.startswith(b"%PDF"):
        raise ValueError(f"{operator.url} did not return a PDF")
    return content


def region_text(pdf: bytes, region: ConceptRegion) -> str:
    """The region's text, as pdfplumber reads it inside the bbox."""
    with pdfplumber.open(io.BytesIO(pdf)) as document:
        page = document.pages[region.page - 1]
        return str(page.crop(region.bbox).extract_text() or "")


def _wanted(
    operator: str, key: list[str] | None, side: Side | None, include_pinned: bool,
    split_file: Path,
) -> tuple[list[str], dict[str, str]]:  # fmt: skip
    """The keys to draft and every key's side."""
    try:
        split = load_split(split_file)
    except (OSError, ValueError) as error:
        raise _fail(f"split file {split_file}: {error}", 2) from error
    if key is not None:
        wanted = sorted({k if ":" in k else concept_key(operator, k) for k in key})
    else:
        wanted = sorted(k for k, s in split.assignments.items() if s == side)
    wanted = [k for k in wanted if k.startswith(f"{operator}:")]
    if not include_pinned:
        wanted = [k for k in wanted if k not in split.pinned_dev]
    unknown = [k for k in wanted if k not in split.assignments]
    if unknown:
        raise _fail(f"not in {split_file.name}: {', '.join(unknown)}", 2)
    if not wanted:
        raise _fail("no key to draft", 2)
    return wanted, dict(split.assignments)


@gold_app.command()
def draft(
    operator: Annotated[str, typer.Option("--operator", help="Operator id (operators.yaml).")],
    key: Annotated[
        list[str] | None, typer.Option("--key", help="A concept key or number hint to draft.")
    ] = None,
    side: Annotated[
        Side | None, typer.Option("--side", help="Draft every key of this side.")
    ] = None,
    include_pinned: Annotated[
        bool, typer.Option("--include-pinned", help="Also draft the pinned dev keys.")
    ] = False,
    image: Annotated[bool, typer.Option(help="Send the rendered region too.")] = True,
    dpi: Annotated[int, typer.Option(min=72, max=300)] = 150,
    max_eur: Annotated[float, typer.Option("--max-eur", help="Stop at this spend.")] = 0.5,
    split_file: Annotated[Path, typer.Option("--split-file")] = GOLD_SPLIT_FILE,
) -> None:
    """Draft concepts of --operator with the gold_draft role and store them, unverified.

    Give --key (repeatable) or --side. Pinned dev keys (labelled from scratch, MKC-25) are
    skipped unless --include-pinned; a verified key is skipped before any call."""
    if (key is None) == (side is None):
        raise _fail("give exactly one of --key and --side", 2)
    if operator not in SEGMENTERS:
        raise _fail(f"no segmenter for operator {operator!r}", 2)
    wanted, sides = _wanted(operator, key, side, include_pinned, split_file)
    settings = get_settings()
    try:
        config = models_config(settings)
        ensure_independent(config)
    except ModelError as error:
        raise _fail(str(error), 2) from error
    pdf = fetch_catalogue(operator)
    digest = hashlib.sha256(pdf).hexdigest()
    regions = {
        concept_key(operator, r.number_hint): r for r in SEGMENTERS[operator](pdf) if r.number_hint
    }
    missing = [k for k in wanted if k not in regions]
    if missing:
        raise _fail(f"not in the catalogue {digest[:12]}: {', '.join(missing)}", 2)
    client = make_client(settings)
    sessions = _sessions()
    verified = _verified(sessions, wanted)
    total, failed = 0.0, 0
    for k in wanted:
        if k in verified:
            typer.echo(f"{k}: verified by {verified[k]}, skipped (no call)")
            continue
        if total >= max_eur:
            typer.echo(f"total: {total:.6f} EUR")
            raise _fail(f"stopped: spend {total:.6f} EUR reached --max-eur {max_eur}", 1)
        region = regions[k]
        images: tuple[Image, ...] = ()
        if image:
            png = render_region(pdf, region.page, region.bbox, dpi).png
            images = (Image(media_type="image/png", data=png),)
        try:
            made = draft_concept(client, config, key=k, text=region_text(pdf, region),
                                 images=images, document=digest, page=region.page)  # fmt: skip
        except (ModelError, ValueError) as error:  # the provider may still have charged
            failed += 1
            typer.echo(f"{k}: failed, cost unknown: {type(error).__name__}: {error}"[:500])
            continue
        total += made.cost_eur
        made.payload["source"] = {"document": digest, "page": region.page}  # harness facts
        try:
            with sessions.begin() as session:
                store_gold_draft(session, made, split=sides[k])
            note = "stored"
        except (VerifiedItem, FactsOnlyError) as error:
            note = f"not stored: {error}"
        typer.echo(f"{k}: {made.drafted_by}, {made.cost_eur:.6f} EUR, {note}")
    typer.echo(f"total: {total:.6f} EUR for {len(wanted)} keys, {failed} failed calls")
    if failed:
        raise typer.Exit(1)


def _verified(sessions: sessionmaker[Session], keys: list[str]) -> dict[str, str]:
    """The keys whose drafted item is verified, with who verified it."""
    with sessions() as session:
        rows = session.execute(
            select(GoldItem.key, GoldItem.verified_by).where(
                GoldItem.kind == "concept",
                GoldItem.blind.is_(False),
                GoldItem.key.in_(keys),
                GoldItem.verified_by.is_not(None),
            )
        ).all()
    return {key: str(by) for key, by in rows}


# --- export and import -------------------------------------------------------------------


@gold_app.command("export")
def export_(
    out: Annotated[Path, typer.Option("--out", help="The JSON file to write.")],
    blind: Annotated[bool, typer.Option("--blind", help="Blind items, no draft.")] = False,
    key: Annotated[list[str] | None, typer.Option("--key", help="Only these keys.")] = None,
) -> None:
    """Write gold items as JSON for verification (with --blind: blind items to label)."""
    try:
        with _sessions().begin() as session:
            document = export_items(session, blind=blind, keys=key)
    except GoldFileError as error:
        raise _fail("export refused: " + "; ".join(error.problems), 1) from error
    text = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    out.write_bytes(text.encode("utf-8"))
    typer.echo(f"{out}: {len(document['items'])} items")


@gold_app.command("import")
def import_(
    file: Path,
    verified_by: Annotated[
        str, typer.Option("--verified-by", help="Who verified the items (required).")
    ],
) -> None:
    """Store the verified items of FILE: all or nothing, idempotent by key."""
    try:
        document: Any = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise _fail(f"{file}: {error}", 2) from error
    try:
        with _sessions().begin() as session:
            result = import_items(session, document, verified_by=verified_by)
    except GoldFileError as error:
        raise _fail("import refused, nothing stored: " + "; ".join(error.problems), 2) from error
    typer.echo(f"{result.verified} items verified by {verified_by}, "
               f"{result.skipped} blind items without a label skipped")  # fmt: skip
