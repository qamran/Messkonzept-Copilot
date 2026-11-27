"""MKC-46: the decision path keeps the model rules (AGENTS.md "Model rules").

`langchain-typesafe` calls a provider over HTTP (with `httpx2`), so like every provider package
it may be imported only by the provider factory. The shared list in `tests/models/guards.py`
does not name it yet, so this lane checks it here, with kept bad samples.
"""

import ast
from pathlib import Path

import pytest

from tests.models.guards import PROVIDER_FACTORY, _imported_modules, _in

SRC = Path(__file__).resolve().parents[2] / "src"
DECISION_PROVIDER_MODULES = ("langchain_typesafe", "httpx2")


def decision_provider_imports(name: str, source: str) -> list[str]:
    if name == PROVIDER_FACTORY:
        return []
    tree = ast.parse(source, filename=name)
    return sorted(
        f"{name}:{line}: imports {module}"
        for line, module in _imported_modules(tree)
        if _in(module, DECISION_PROVIDER_MODULES)
    )


BAD_SOURCES = [
    "import langchain_typesafe\n",
    "from langchain_typesafe import TypeSafeClassifier\n",
    "from langchain_typesafe.client import parse_response\n",
    "import httpx2\n",
    "def f():\n    from langchain_typesafe import Noul\n",
    "import importlib\nimportlib.import_module('langchain_typesafe')\n",
]


@pytest.mark.parametrize("source", BAD_SOURCES)
def test_typesafe_import_outside_the_factory_is_found(source: str) -> None:
    assert decision_provider_imports("mkc/decision/client.py", source) != []


@pytest.mark.parametrize("source", BAD_SOURCES)
def test_typesafe_import_in_the_factory_passes(source: str) -> None:
    assert decision_provider_imports(PROVIDER_FACTORY, source) == []


def test_langchain_core_decisions_import_passes() -> None:
    source = "from langchain_core.decisions import BaseDecisionModel, Noul\n"
    assert decision_provider_imports("mkc/decision/client.py", source) == []


def test_repo_imports_typesafe_only_in_the_factory() -> None:
    found = [
        hit
        for path in sorted(SRC.rglob("*.py"))
        for hit in decision_provider_imports(
            path.relative_to(SRC).as_posix(), path.read_text(encoding="utf-8")
        )
    ]
    assert found == []
