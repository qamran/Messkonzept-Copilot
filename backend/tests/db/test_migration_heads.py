"""MKC-168.3: `main` never has two Alembic heads (decision 61).

Parallel lanes each add a migration with `down_revision` set to `main`'s head when the
branch was cut. When two such PRs merge, the second one must be re-chained; this test is
what fails until it is. Heads are a property of the versions folder, so no database is used.
"""

import re
import shutil
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

BACKEND = Path(__file__).resolve().parents[2]
MIGRATIONS = BACKEND / "migrations"


def migration_heads(script_location: Path) -> list[str]:
    config = Config()
    config.set_main_option("script_location", str(script_location))
    return sorted(ScriptDirectory.from_config(config).get_heads())


def test_single_migration_head() -> None:
    heads = migration_heads(MIGRATIONS)
    assert len(heads) == 1, (
        f"two or more migration heads {heads}: re-chain the newer revision's down_revision "
        "onto the other head (AGENTS.md, Parallel lanes)"
    )


def _revision(path: Path, field: str) -> str:
    match = re.search(rf'^{field}: str(?: \| None)? = "([^"]+)"', path.read_text("utf-8"), re.M)
    assert match, (path, field)
    return match.group(1)


def test_a_forked_revision_makes_two_heads(tmp_path: Path) -> None:
    copy = tmp_path / "migrations"
    shutil.copytree(MIGRATIONS, copy, ignore=shutil.ignore_patterns("__pycache__"))
    (head,) = migration_heads(copy)
    head_file = next(
        p for p in (copy / "versions").glob("*.py") if _revision(p, "revision") == head
    )
    parent = _revision(head_file, "down_revision")
    (copy / "versions" / "9999_fork.py").write_text(
        f'revision = "9999fork"\ndown_revision = "{parent}"\n'
        "branch_labels = None\ndepends_on = None\n\n\n"
        "def upgrade() -> None:\n    pass\n\n\ndef downgrade() -> None:\n    pass\n",
        encoding="utf-8",
    )
    assert migration_heads(copy) == sorted([head, "9999fork"])
