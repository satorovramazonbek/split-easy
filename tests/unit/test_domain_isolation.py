"""The domain layer must not depend on web or database frameworks (NFR-4)."""

import ast
from pathlib import Path

import pytest

DOMAIN_DIR = Path(__file__).resolve().parents[2] / "app" / "domain"
FORBIDDEN = {"fastapi", "sqlalchemy", "starlette", "pydantic", "jinja2"}


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module.split(".")[0])
    return modules


@pytest.mark.parametrize(
    "path", sorted(DOMAIN_DIR.glob("*.py")), ids=lambda path: path.name
)
def test_domain_module_does_not_import_frameworks(path: Path) -> None:
    assert imported_modules(path).isdisjoint(FORBIDDEN)
