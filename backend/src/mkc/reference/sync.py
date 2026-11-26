"""Load the LBS reference data into the table `lbs_structure` (MKC-12, decision 50).

`mkc-load-lbs` reads backend/data/lbs_structures.yaml and upserts one row per structure,
so running it again changes nothing. It runs by hand for now; the first ticket that
reads the table runs it on deploy.
"""

import sys
from dataclasses import asdict
from typing import Any

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from mkc.db.models import LbsStructureRow
from mkc.db.session import get_session
from mkc.reference.lbs import DEFAULT_PATH, LbsSource, LbsStructure, load_lbs, load_lbs_source


def _objects(structure: LbsStructure) -> list[dict[str, Any]]:
    out = []
    for obj in structure.objects:
        row = asdict(obj)
        row["referenz_melo"] = list(obj.referenz_melo)
        row["referenz_nelo"] = list(obj.referenz_nelo)
        out.append(row)
    return out


def sync_lbs(session: Session, structures: list[LbsStructure], source: LbsSource) -> int:
    """Insert or update one row per structure; returns the number of rows written."""
    version = f"{source.version} ({source.edition})"
    rows = [
        {
            "code": s.code,
            "bezeichnung": s.bezeichnung,
            "objects": _objects(s),
            "source": f"{source.url}#page={s.page}",
            "version": version,
        }
        for s in structures
    ]
    if not rows:
        return 0
    statement = insert(LbsStructureRow).values(rows)
    statement = statement.on_conflict_do_update(
        index_elements=[LbsStructureRow.code],
        set_={
            name: statement.excluded[name]
            for name in ("bezeichnung", "objects", "source", "version")
        },
    )
    session.execute(statement)
    return len(rows)


def main() -> int:
    structures = load_lbs(DEFAULT_PATH)
    source = load_lbs_source(DEFAULT_PATH)
    with get_session() as session:
        written = sync_lbs(session, structures, source)
    print(f"lbs_structure: {written} rows from {source.edition}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
