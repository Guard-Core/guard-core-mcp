"""plugin/plugin.json carries the package version, and bump_version keeps it so.

plugin.json said 0.1.0 while the package, server.json and the docs said 2.0.0,
because the bump script never touched it.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path
from types import ModuleType

import pytest

from guard_core_mcp import __version__

ROOT = Path(__file__).resolve().parent.parent


def _bump_script() -> ModuleType:
    path = ROOT / ".github" / "scripts" / "bump_version.py"
    spec = importlib.util.spec_from_file_location("bump_version_for_plugin_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_plugin_json_version_matches_the_package_version() -> None:
    plugin = json.loads((ROOT / "plugin" / "plugin.json").read_text())
    assert plugin["version"] == __version__


def test_every_version_file_agrees() -> None:
    pyproject = re.search(
        r'^version = "([^"]+)"', (ROOT / "pyproject.toml").read_text(), re.M
    )
    server = json.loads((ROOT / "server.json").read_text())
    assert pyproject is not None
    assert {pyproject.group(1), server["version"]} == {__version__}


def test_bump_script_updates_plugin_json_and_keeps_its_format(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "plugin").mkdir()
    original = (ROOT / "plugin" / "plugin.json").read_text()
    (tmp_path / "plugin" / "plugin.json").write_text(
        original.replace(f'"version": "{__version__}"', '"version": "0.1.0"', 1)
    )
    bump = _bump_script()
    monkeypatch.setattr(bump, "PROJECT_ROOT", tmp_path)

    assert bump.update_plugin_json(__version__) is True
    assert (tmp_path / "plugin" / "plugin.json").read_text() == original

    assert bump.update_plugin_json(__version__) is True
    assert (tmp_path / "plugin" / "plugin.json").read_text() == original


def test_bump_script_skips_a_missing_plugin_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bump = _bump_script()
    monkeypatch.setattr(bump, "PROJECT_ROOT", tmp_path)

    assert bump.update_plugin_json("9.9.9") is True
