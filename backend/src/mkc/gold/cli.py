"""`mkc gold split|draft|export|import` (MKC-24, feature 33, design 11.1).

- `split` writes the dev/test split file from a YAML list of concept keys.
- `draft` fetches an operator's public catalogue into memory (never to disk), segments it,
  and drafts the chosen concepts with the `gold_draft` role; each call's cost is printed.
- `export` writes gold items as JSON for the user to verify; `--blind` writes empty blind
  items for the given keys, with no draft in them.
- `import` reads that file back; `--verified-by` names the person who verified it.

Exit codes: 0 done, 1 refused (a data rule, a verified item, a spend cap), 2 bad input.
"""

from pathlib import Path
from typing import Annotated

import typer
import yaml

from mkc.gold.split import GOLD_SPLIT_FILE, dump_split, split_keys

gold_app = typer.Typer(no_args_is_help=True, help="Gold data: split, draft, export, import.")


def _fail(message: str, code: int) -> typer.Exit:
    typer.echo(message, err=True)
    return typer.Exit(code)


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
