"""The dependency rule, asserted rather than trusted.

No module in the domain or the use cases may import a framework: aiohttp, aiortc,
av and pjsua2 belong to the outer layers and are reached through the ports. The
ruff import ban enforces this too; this test proves it from the source itself, so
a rule accidentally loosened in a config still fails here.
"""

from __future__ import annotations

import ast
from pathlib import Path

import urmet_gateway.domain as domain_pkg
import urmet_gateway.usecases as usecases_pkg

BANNED = frozenset({"aiohttp", "aiortc", "av", "pjsua2"})


def _imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])
    return roots


def _offenders(package: object) -> dict[str, list[str]]:
    directory = Path(package.__file__).parent  # type: ignore[attr-defined]
    found: dict[str, list[str]] = {}
    for path in sorted(directory.glob("*.py")):
        hit = _imported_roots(path) & BANNED
        if hit:
            found[path.name] = sorted(hit)
    return found


def test_no_usecases_module_imports_a_banned_package() -> None:
    assert _offenders(usecases_pkg) == {}


def test_no_domain_module_imports_a_banned_package() -> None:
    assert _offenders(domain_pkg) == {}
