"""The Python family's versions live in one table, and everything else reads it.

The registry listed the 4.4.x family while the code under it was 5.0.0, and
docs/tools.md carried its own copy of the versions. These tests keep the table,
the registry, the dependency floors and the documented `versions` example in step.
"""

from __future__ import annotations

import re
from pathlib import Path

from json_access import get, parse_json
from packaging.requirements import Requirement
from packaging.version import Version

from guard_core_mcp import __version__
from guard_core_mcp import docs as docs_module
from guard_core_mcp.ecosystem import PYTHON_FAMILY_VERSIONS, REGISTRY
from guard_core_mcp.json_types import JsonValue

ROOT = Path(__file__).resolve().parent.parent


def _registry_python_versions() -> dict[str, str]:
    python = REGISTRY.languages["python"]
    return {
        python.engine.package: python.engine.version,
        python.agent.package: python.agent.version,
        **{adapter.package: adapter.version for adapter in python.adapters},
    }


def _documented_versions_example() -> JsonValue:
    text = (ROOT / "docs" / "tools.md").read_text()
    section = text.split("`versions`\n----------", 1)[1]
    block = re.search(r"```json\n(.*?)\n```", section, re.S)
    assert block is not None, "docs/tools.md has no versions example"
    return parse_json(block.group(1))


def test_the_registry_python_entries_are_exactly_the_table() -> None:
    assert _registry_python_versions() == PYTHON_FAMILY_VERSIONS


def test_the_table_satisfies_the_dependency_floors_in_pyproject() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text()
    floors = [
        Requirement(match)
        for match in re.findall(
            r'^\s+"((?:guard-core|fastapi-guard|guard-agent)[^"]*)"', pyproject, re.M
        )
    ]
    assert {r.name for r in floors} == {"guard-core", "fastapi-guard", "guard-agent"}
    for requirement in floors:
        assert requirement.specifier.contains(
            Version(PYTHON_FAMILY_VERSIONS[requirement.name])
        ), f"{requirement} excludes the registry's {requirement.name}"


def test_the_documented_versions_example_matches_the_package_and_manifests() -> None:
    example = _documented_versions_example()

    assert get(example, "guard_core_mcp") == __version__
    assert get(example, "docs_bundled_for") == {
        package: entry["version"] for package, entry in docs_module.manifest().items()
    }
    assert get(example, "knowledge_bundled_for") == {
        package: entry["version"]
        for package, entry in docs_module.knowledge_manifest().items()
    }


def test_the_documented_installed_versions_are_the_registry_versions() -> None:
    installed = get(_documented_versions_example(), "installed")
    assert installed == {
        package: PYTHON_FAMILY_VERSIONS[package]
        for package in ("guard-core", "fastapi-guard", "guard-agent")
    }
