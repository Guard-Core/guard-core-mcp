import builtins
from collections.abc import Mapping, Sequence
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock

import pytest

from guard_core_mcp.ecosystem import REGISTRY


def served_python_snippets() -> list[tuple[str, str]]:
    python = REGISTRY.languages["python"]
    snippets = [(f"adapter {a.framework}", a.snippet) for a in python.adapters]
    return [*snippets, ("agent", python.agent.snippet)]


@pytest.mark.parametrize(
    ("label", "snippet"), served_python_snippets(), ids=lambda value: str(value)[:20]
)
def test_every_served_python_snippet_executes(
    label: str, snippet: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    real_import = builtins.__import__
    adapters_not_installed = {"flaskapi_guard", "djangoapi_guard", "tornadoapi_guard"}

    def import_or_stub(
        name: str,
        globals: Mapping[str, object] | None = None,
        locals: Mapping[str, object] | None = None,
        fromlist: Sequence[str] = (),
        level: int = 0,
    ) -> ModuleType:
        if name in adapters_not_installed:
            return MagicMock()
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", import_or_stub)
    namespace: dict[str, object] = {"__name__": "served_snippet", "app": MagicMock()}

    exec(compile(snippet, f"<served snippet: {label}>", "exec"), namespace)
