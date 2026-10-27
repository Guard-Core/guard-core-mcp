import ast
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_PACKAGE = _ROOT / "guard_core_mcp"


def _names_any(path: Path) -> bool:
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Name) and node.id == "Any":
            return True
        if isinstance(node, ast.Attribute) and node.attr == "Any":
            return True
        if isinstance(node, ast.ImportFrom) and any(
            alias.name == "Any" for alias in node.names
        ):
            return True
    return False


def test_no_module_names_any() -> None:
    regained = [
        str(path.relative_to(_ROOT))
        for path in sorted(_PACKAGE.rglob("*.py"))
        if _names_any(path)
    ]
    assert not regained, f"D-189 ratchet: modules that regained Any: {regained}"


def test_mypy_forbids_explicit_any_with_no_module_exempt() -> None:
    text = (_ROOT / "pyproject.toml").read_text()
    mypy_table = text.split("[tool.mypy]", 1)[1].split("\n[", 1)[0]
    assert re.search(r"^disallow_any_explicit = true$", mypy_table, re.MULTILINE)
    assert not re.search(r"disallow_any_explicit = false", text), (
        "D-189 ratchet: a mypy override exempts a module from the Any gate"
    )
