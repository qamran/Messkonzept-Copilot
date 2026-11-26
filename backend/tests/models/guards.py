"""Checks behind the model-rule tests (MKC-13.1). They parse code instead of matching text,
so comments and strings that merely mention a name do not count, and aliases still do."""

import ast
import re

PROVIDER_FACTORY = "mkc/models/providers.py"
"""The one module (relative to `src/`) that may import provider packages."""

AGENT_NAMES = frozenset({"create_agent", "AgentExecutor", "create_react_agent"})
"""LangChain and LangGraph agent APIs that the harness must not use (ADR 001)."""

PROVIDER_MODULES = (
    "anthropic",
    "openai",
    "openrouter",
    "llama_api_client",
    "google.genai",
    "google.generativeai",
    "langchain_openrouter",
    "langchain_anthropic",
    "langchain_google_genai",
    "langchain_meta",
    "langchain_openai",
)

_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*(.*)$")
_PIN = re.compile(r"^==\s*[A-Za-z0-9.+!-]+$")
_LOCK_NAME = re.compile(r'^name = "([^"]+)"$', re.MULTILINE)


def _normalise(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def unpinned_langchain(requirements: list[str]) -> list[str]:
    """Requirements for a `langchain*` package that are not one exact `==` pin."""
    found = []
    for requirement in requirements:
        match = _NAME.match(requirement.split(";", 1)[0])
        if not match or not _normalise(match.group(1)).startswith("langchain"):
            continue
        spec = match.group(2).strip()
        if not _PIN.match(spec) or "*" in spec:
            found.append(requirement)
    return found


def forbidden_locked_packages(lock_text: str) -> list[str]:
    """LangGraph packages and the `langchain` meta-package (which depends on LangGraph)."""
    names = {_normalise(name) for name in _LOCK_NAME.findall(lock_text)}
    return sorted(n for n in names if n == "langchain" or n.startswith("langgraph"))


def _dynamic_imports(tree: ast.AST) -> list[tuple[int, str]]:
    """Module names passed as a constant to `__import__` or `import_module`."""
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        func = node.func
        name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
        first = node.args[0]
        if (
            name in {"__import__", "import_module"}
            and isinstance(first, ast.Constant)
            and isinstance(first.value, str)
        ):
            found.append((node.lineno, first.value))
    return found


def _imported_modules(tree: ast.AST) -> list[tuple[int, str]]:
    """Every absolute module a file imports, including `from a import b` as `a.b`."""
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.append((node.lineno, node.module))
            found.extend((node.lineno, f"{node.module}.{alias.name}") for alias in node.names)
    return found + _dynamic_imports(tree)


def _in(module: str, roots: tuple[str, ...]) -> bool:
    return any(module == root or module.startswith(root + ".") for root in roots)


def agent_api_uses(name: str, source: str) -> list[str]:
    """LangGraph imports and any use of an agent API name in one file."""
    tree = ast.parse(source, filename=name)
    hits = [
        f"{name}:{line}: imports {module}"
        for line, module in _imported_modules(tree)
        if _in(module, ("langgraph",))
    ]
    for node in ast.walk(tree):
        used = None
        if isinstance(node, ast.Name):
            used = node.id
        elif isinstance(node, ast.Attribute):
            used = node.attr
        elif isinstance(node, ast.alias):
            used = node.name.rsplit(".", 1)[-1]
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            used = node.name
        if used in AGENT_NAMES:
            hits.append(f"{name}:{getattr(node, 'lineno', '?')}: uses {used}")
    return hits


def provider_imports(name: str, source: str) -> list[str]:
    """Provider package imports in any file other than the provider factory."""
    if name == PROVIDER_FACTORY:
        return []
    tree = ast.parse(source, filename=name)
    return sorted(
        {
            f"{name}:{line}: imports {module}"
            for line, module in _imported_modules(tree)
            if _in(module, PROVIDER_MODULES)
        }
    )
