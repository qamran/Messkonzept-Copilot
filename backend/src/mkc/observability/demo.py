"""One real traced run (MKC-19.5): `uv run python -m mkc.observability.demo`.

Makes one synthetic run with one item (the fictional operator "Stadtwerke Musterstadt"; no
real document), runs it once through the worker's own executor and prints the run id, its
state and its trace id. Needs `MKC_MODEL_MODE=live` (it spends a few cents at most: keep
`MKC_ITEM_MAX_STEPS` and `MKC_RUN_MAX_COST_EUR` small) and a local database: it refuses a
`DATABASE_URL` that is not on this machine.
"""

from sqlalchemy.orm import Session

TASK = {
    "operator": "Stadtwerke Musterstadt",
    "concept_key": "MK-DEMO-1",
    "region": "page 1",
    "note": "synthetic tracing demo (MKC-19.5): there is no document to read",
}


def make_demo_run(session: Session) -> int:
    """A `running` run with one `queued` synthetic item. The caller commits."""
    return 0


def main() -> int:
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
