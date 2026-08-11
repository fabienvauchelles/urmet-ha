"""The dependency rule, asserted rather than trusted.

The nested ``ruff.toml`` files carry the ban list, one per layer. This test says
the same thing a second time, from the source itself, so a rule quietly loosened
in a config still fails the gate. It is deliberately a duplicate statement and
not a reader of those files: a test that parsed the config would go quiet with it.

Two things the earlier version got wrong and this one does not. The walk is
recursive, so a subpackage under ``domain`` or ``usecases`` is covered like the
top of it. And the banned set is the whole list the ruff files declare, the inner
layers of the project included, not the four frameworks alone.
"""

from __future__ import annotations

import ast
from pathlib import Path

import urmet_gateway.domain as domain_pkg
import urmet_gateway.usecases as usecases_pkg

FRAMEWORKS = frozenset({"aiohttp", "aiortc", "av", "pjsua2"})

# What each inner layer may not import, mirroring its ruff.toml banned-api list.
# domain is innermost: every other module of the project is banned to it.
BANNED_BY_LAYER: dict[str, frozenset[str]] = {
    "domain": FRAMEWORKS
    | {
        "urmet_gateway.usecases",
        "urmet_gateway.sip",
        "urmet_gateway.media",
        "urmet_gateway.http",
        "urmet_gateway.main",
        "urmet_gateway.runtime",
    },
    "usecases": FRAMEWORKS
    | {
        "urmet_gateway.sip",
        "urmet_gateway.media",
        "urmet_gateway.http",
        "urmet_gateway.main",
        "urmet_gateway.runtime",
    },
}


def _imported_modules(path: Path) -> set[str]:
    """Every module this file imports, by full dotted name."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules.add(node.module)
    return modules


def _hits(imported: str, banned: frozenset[str]) -> set[str]:
    """The banned entries this import falls under, itself or a subpackage of one."""
    return {name for name in banned if imported == name or imported.startswith(f"{name}.")}


def _offenders(package: object, banned: frozenset[str]) -> dict[str, list[str]]:
    directory = Path(package.__file__).parent  # type: ignore[attr-defined]
    found: dict[str, list[str]] = {}
    for path in sorted(directory.rglob("*.py")):
        hit = {name for imported in _imported_modules(path) for name in _hits(imported, banned)}
        if hit:
            found[str(path.relative_to(directory))] = sorted(hit)
    return found


def test_no_usecases_module_imports_a_banned_package() -> None:
    assert _offenders(usecases_pkg, BANNED_BY_LAYER["usecases"]) == {}


def test_no_domain_module_imports_a_banned_package() -> None:
    assert _offenders(domain_pkg, BANNED_BY_LAYER["domain"]) == {}
