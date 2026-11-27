"""MKC-15 criterion 1: every run or item state write in `src/mkc` goes through `transition`.

The check parses code. A state write is:

- an assignment to an attribute named `state`, or `setattr(..., "state", ...)`
- a `state=` keyword, a `**` argument or a dict with a `"state"` key in a `.values(...)` call

Its value must be `transition(...)` or `transition(...).value`. Creating a row is not a
transition, but it must start in the initial state: `Item(state=...)` only `queued`,
`Run(state=...)` only `running`.

Known gaps (not parsed): raw SQL text, bulk `execute(update(Item), [rows])`, and a
`transition` call with a hard-coded current state.
"""

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src" / "mkc"

EXEMPT = {"backup.py"}
"""`backup_runs.state` is the backup job's own status (MKC-11), not a run or item state."""


INITIAL = {"Item": "queued", "Run": "running"}
"""The state a new row must start in."""


def _is_initial(node: ast.expr, initial: str) -> bool:
    if isinstance(node, ast.Attribute) and node.attr == "value":
        node = node.value
    if isinstance(node, ast.Constant):
        return bool(node.value == initial)
    return isinstance(node, ast.Attribute) and node.attr == initial.upper()


def _is_transition(node: ast.expr) -> bool:
    if isinstance(node, ast.Attribute) and node.attr == "value":
        node = node.value
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "transition"
    )


def unguarded_state_writes(source: str) -> list[int]:
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Assign | ast.AnnAssign | ast.AugAssign):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Attribute) and target.attr == "state":
                    value = None if isinstance(node, ast.AugAssign) else node.value
                    if value is None or not _is_transition(value):
                        found.append(node.lineno)
        elif isinstance(node, ast.Call):
            func = node.func
            if (
                isinstance(func, ast.Name)
                and func.id == "setattr"
                and len(node.args) == 3
                and isinstance(node.args[1], ast.Constant)
                and node.args[1].value == "state"
                and not _is_transition(node.args[2])
            ):
                found.append(node.lineno)
            if isinstance(func, ast.Attribute) and func.attr == "values":
                for kw in node.keywords:
                    if kw.arg is None or (kw.arg == "state" and not _is_transition(kw.value)):
                        found.append(node.lineno)
                for arg in node.args:
                    if isinstance(arg, ast.Dict) and any(
                        isinstance(k, ast.Constant) and k.value == "state" for k in arg.keys
                    ):
                        found.append(node.lineno)
            if isinstance(func, ast.Name) and func.id in INITIAL:
                for kw in node.keywords:
                    if kw.arg == "state" and not _is_initial(kw.value, INITIAL[func.id]):
                        found.append(node.lineno)
    return found


@pytest.mark.parametrize(
    "source",
    [
        "item.state = 'failed'",
        "item.state = ItemState.FAILED.value",
        "run.state: str = 'done'",
        "setattr(item, 'state', 'failed')",
        "session.execute(update(Item).values(state='failed'))",
        "item.state += 'x'",
        "Item(run_id=1, state='failed')",
        "Run(state=RunState.DONE.value)",
        "session.execute(update(Item).values(**fields))",
        "session.execute(update(Item).values({'state': 'failed'}))",
    ],
)
def test_unguarded_writes_are_found(source: str) -> None:
    assert unguarded_state_writes(source) == [1]


@pytest.mark.parametrize(
    "source",
    [
        "item.state = transition(ItemState(item.state), ItemState.FAILED).value",
        "run.state = transition(current, target)",
        "update(Item).values(state=transition(a, b).value)",
        "app.state.verifier = make()",
        "# item.state = 'failed'",
        "x = 'item.state = 1'",
        "if item.state == 'queued': pass",
        "Item(run_id=1, state='queued')",
        "Item(run_id=1, state=ItemState.QUEUED.value)",
        "Run(state='running')",
        "Run(state=RunState.RUNNING)",
    ],
)
def test_guarded_writes_and_non_writes_pass(source: str) -> None:
    assert unguarded_state_writes(source) == []


def test_repo_writes_run_and_item_states_only_through_transition() -> None:
    found = {
        f"{path.relative_to(SRC)}:{line}"
        for path in SRC.rglob("*.py")
        if path.name not in EXEMPT
        for line in unguarded_state_writes(path.read_text(encoding="utf-8"))
    }
    assert found == set()


def test_the_exempt_module_really_has_backup_state_writes() -> None:
    # Keeps the exemption honest: if backup.py stops writing states, drop it from EXEMPT.
    assert unguarded_state_writes((SRC / "backup.py").read_text(encoding="utf-8"))
