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


KNOWLEDGE_DIR = Path(__file__).parent.parent / "guard_core_mcp" / "_knowledge"


def test_typescript_agent_snippet_builds_the_agent_from_a_plain_config_object() -> None:
    # guardagent 3.2.4 exports AgentConfig as a type only, so AgentConfig.create()
    # is a TypeError at runtime; the documented form is new GuardAgent({...}).
    served = [
        REGISTRY.languages["typescript"].agent.snippet,
        (KNOWLEDGE_DIR / "guard-agent-ts" / "index.md").read_text(encoding="utf-8"),
    ]
    for text in served:
        assert "AgentConfig.create" not in text
        assert "new GuardAgent({" in text


@pytest.mark.parametrize(
    ("language", "timestamp_marker"),
    [("typescript", "timestamp: new Date()"), ("php", "'timestamp' =>")],
)
def test_typescript_and_php_agent_events_carry_the_required_timestamp(
    language: str, timestamp_marker: str
) -> None:
    # guardagent 3.2.4 and guard-agent-php 3.2.4 drop an event without a
    # timestamp ("timestamp is required"), so the served event must set one.
    snippet = REGISTRY.languages[language].agent.snippet
    assert timestamp_marker in snippet


def test_the_saas_page_says_the_python_signing_defect_is_fixed_since_3_0_2() -> None:
    # guard-agent v3.0.1 signs the compressed body, v3.0.2 and later the raw body.
    page = (KNOWLEDGE_DIR / "guard-core-app" / "index.md").read_text(encoding="utf-8")
    assert "That defect is fixed as of 3.0.2" in page
    assert "Pin >=3.0.2" in page
    assert "guard-agent 3.0.0 (Python) signs after compression" not in page
