import ast
from collections.abc import Iterator
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src" / "foodiegram"
_FORBIDDEN_ROOTS = frozenset({"sqlmodel", "sqlalchemy"})


def _imported_modules(path: Path) -> Iterator[str]:
    """Yield every module name imported by the Python file at path."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            yield node.module


def test_orm_imports_confined_to_storage() -> None:
    """Only storage/ may import sqlmodel/sqlalchemy — the D4 boundary."""
    offenders = [
        f"{path.relative_to(_SRC)}: {module}"
        for path in _SRC.rglob("*.py")
        if "storage" not in path.relative_to(_SRC).parts
        for module in _imported_modules(path)
        if module.split(".", 1)[0] in _FORBIDDEN_ROOTS
    ]

    assert not offenders, f"ORM imports leaked outside storage/: {offenders}"
