"""MKC-19.5: the demo run is synthetic, local and live only."""

from collections import Counter

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from mkc.db.models import Item, Run
from mkc.observability import demo


def test_make_demo_run_is_one_synthetic_item(engine: Engine) -> None:
    with Session(engine) as session:
        run_id = demo.make_demo_run(session)
        session.commit()
        run = session.get_one(Run, run_id)
        (item,) = session.scalars(select(Item).where(Item.run_id == run_id))
        assert (run.state, item.state) == ("running", "queued")
        assert item.task["operator"] == "Stadtwerke Musterstadt"  # fictional (data rules)


@pytest.mark.parametrize(
    ("env", "message"),
    [
        ({"MKC_MODEL_MODE": "replay"}, "MKC_MODEL_MODE=live"),
        (
            {"MKC_MODEL_MODE": "live", "DATABASE_URL": "postgresql+psycopg://u:p@127.0.0.1:5433/x"},
            "Langfuse keys",
        ),
        (
            {
                "MKC_MODEL_MODE": "live",
                "DATABASE_URL": "postgresql+psycopg://u:p@db.example.com:5432/x",
            },
            "local database",
        ),
    ],
)
def test_main_refuses_without_live_mode_or_local_database(
    env: dict[str, str], message: str, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:  # fmt: skip
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    assert demo.main() == 2
    assert message in capsys.readouterr().err


def test_expected_types_follow_the_run_log_kinds() -> None:
    kinds = ["model", "tool", "model", "tool", "stop", "outage"]
    assert demo.expected_types(kinds) == Counter({"GENERATION": 2, "TOOL": 2, "EVENT": 2})
