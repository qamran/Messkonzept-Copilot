"""MKC-13.1: the model rules of AGENTS.md hold in the code and the dependencies.

- LangChain packages are pinned with `==`.
- No LangGraph and no `langchain` meta-package (it depends on LangGraph) in the lock.
- No agent APIs (`create_agent`, `AgentExecutor`) and no LangGraph import anywhere in `src/`.
- Provider packages are imported only by the provider factory, so every call goes
  through `ModelClient`.

Each rule is tested against kept bad samples as well as against the repo.
"""

from pathlib import Path

import pytest

from tests.models.guards import (
    AGENT_NAMES,
    PROVIDER_FACTORY,
    agent_api_uses,
    forbidden_locked_packages,
    provider_imports,
    unpinned_langchain,
)

BACKEND = Path(__file__).resolve().parents[2]
SRC = BACKEND / "src"


def _sources() -> list[tuple[str, str]]:
    return [
        (path.relative_to(SRC).as_posix(), path.read_text(encoding="utf-8"))
        for path in sorted(SRC.rglob("*.py"))
    ]


# --- pins -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "requirement",
    [
        "langchain-core>=1.8.5",
        "langchain-core",
        "langchain-openrouter~=0.3.0",
        "langchain_anthropic>=1.7,<2",
        "LangChain-Meta==0.5.*",
    ],
)
def test_unpinned_langchain_requirement_is_found(requirement: str) -> None:
    assert unpinned_langchain([requirement]) == [requirement]


def test_pinned_and_other_requirements_pass() -> None:
    assert unpinned_langchain(["langchain-core==1.8.5", "fastapi>=0.115"]) == []


def test_repo_langchain_dependencies_are_pinned() -> None:
    import tomllib

    project = tomllib.loads((BACKEND / "pyproject.toml").read_text(encoding="utf-8"))
    assert unpinned_langchain(project["project"]["dependencies"]) == []


# --- lock -----------------------------------------------------------------------------


def test_langgraph_and_meta_package_in_lock_are_found() -> None:
    lock = '[[package]]\nname = "langgraph"\n\n[[package]]\nname = "langchain"\n'
    assert forbidden_locked_packages(lock) == ["langchain", "langgraph"]


def test_langgraph_variants_in_lock_are_found() -> None:
    lock = '[[package]]\nname = "langgraph-prebuilt"\n'
    assert forbidden_locked_packages(lock) == ["langgraph-prebuilt"]


def test_langchain_integrations_in_lock_pass() -> None:
    lock = '[[package]]\nname = "langchain-core"\n\n[[package]]\nname = "langchain-openrouter"\n'
    assert forbidden_locked_packages(lock) == []


def test_repo_lock_has_no_langgraph() -> None:
    assert forbidden_locked_packages((BACKEND / "uv.lock").read_text(encoding="utf-8")) == []


# --- agent APIs -----------------------------------------------------------------------

BAD_AGENT_SOURCES = [
    "from langchain.agents import create_agent\n",
    "import langgraph\n",
    "from langgraph.graph import StateGraph\n",
    "import langchain.agents as agents\nagents.create_agent(model)\n",
    "from langchain.agents import AgentExecutor\n",
    "x = __import__('langgraph')\n",
    "import importlib\nimportlib.import_module('langgraph.prebuilt')\n",
    "def create_agent():\n    pass\n",
]


@pytest.mark.parametrize("source", BAD_AGENT_SOURCES)
def test_agent_api_use_is_found(source: str) -> None:
    assert agent_api_uses("bad.py", source) != []


def test_comments_and_strings_about_agents_pass() -> None:
    source = '"""We do not use create_agent."""\n# langgraph is not used\nx = 1\n'
    assert agent_api_uses("ok.py", source) == []


def test_repo_uses_no_agent_api() -> None:
    found = [hit for name, text in _sources() for hit in agent_api_uses(name, text)]
    assert found == []


def test_agent_names_cover_the_rules() -> None:
    assert {"create_agent", "AgentExecutor"} <= AGENT_NAMES


# --- provider imports -----------------------------------------------------------------

BAD_PROVIDER_SOURCES = [
    "import anthropic\n",
    "import openai\n",
    "from openai import OpenAI\n",
    "from google import genai\n",
    "import google.genai\n",
    "from google.genai import Client\n",
    "import openrouter\n",
    "import llama_api_client\n",
    "from langchain_openrouter import ChatOpenRouter\n",
    "from langchain_anthropic import ChatAnthropic\n",
    "from langchain_google_genai import ChatGoogleGenerativeAI\n",
    "from langchain_meta import ChatLlama\n",
    "from langchain_openai import ChatOpenAI\n",
    "import importlib\nimportlib.import_module('anthropic')\n",
    "def f():\n    import openai\n",
]


@pytest.mark.parametrize("source", BAD_PROVIDER_SOURCES)
def test_provider_import_outside_the_factory_is_found(source: str) -> None:
    assert provider_imports("mkc/worker/main.py", source) != []


@pytest.mark.parametrize("source", BAD_PROVIDER_SOURCES)
def test_provider_import_in_the_factory_passes(source: str) -> None:
    assert provider_imports(PROVIDER_FACTORY, source) == []


def test_langchain_core_import_passes_anywhere() -> None:
    source = "from langchain_core.messages import HumanMessage\nimport google.protobuf\n"
    assert provider_imports("mkc/models/client.py", source) == []


def test_repo_imports_providers_only_in_the_factory() -> None:
    found = [hit for name, text in _sources() for hit in provider_imports(name, text)]
    assert found == []
