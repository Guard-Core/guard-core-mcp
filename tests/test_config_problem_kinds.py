"""validate_config returns each guard-core problem with its machine-readable kind.

guard-core 5.x (the floor this package requires) logs a misconfiguration with
``extra={"problems": ((kind, subject), ...)}``; construction_warnings kept only the
message text, so a client had to parse prose to tell an unknown field from a /0
trusted proxy. construction_problems pairs each message with its kinds and
construction_warnings is unchanged.
"""

from __future__ import annotations

import logging

import pytest
from json_access import arr, get, strs, text

import guard_core_mcp.config as config_module
from guard_core_mcp.config import PACKAGE_MODELS, validate_config
from guard_core_mcp.json_types import JsonValue


def _kinds_of(entry: JsonValue) -> list[tuple[str, str | None]]:
    pairs: list[tuple[str, str | None]] = []
    for kind in arr(get(entry, "kinds")):
        subject = get(kind, "subject")
        assert subject is None or isinstance(subject, str)
        pairs.append((text(get(kind, "kind")), subject))
    return pairs


def _entry_for(report: JsonValue, fragment: str) -> JsonValue:
    matching = [
        entry
        for entry in arr(get(report, "construction_problems"))
        if fragment in text(get(entry, "message"))
    ]
    assert len(matching) == 1, f"expected one problem containing {fragment!r}"
    return matching[0]


def test_unknown_field_problem_carries_its_kind_and_subject() -> None:
    report = validate_config({"totally_bogus_field_xyz": True}, package="guard-core")

    entry = _entry_for(report, "unknown field 'totally_bogus_field_xyz'")

    assert _kinds_of(entry) == [("config.unknown_field", "totally_bogus_field_xyz")]


def test_trusted_proxies_prefix_zero_problem_carries_its_kind() -> None:
    report = validate_config({"trusted_proxies": ["0.0.0.0/0"]}, package="guard-core")

    entry = _entry_for(report, "trusted_proxies contains a /0 network")

    assert _kinds_of(entry) == [("trusted_proxies.prefix_zero", None)]


def test_changed_defaults_notice_lists_one_kind_per_changed_default() -> None:
    report = validate_config({}, package="guard-core")

    entry = _entry_for(report, "changed defaults that this configuration leaves unset")

    kinds = [kind for kind, _ in _kinds_of(entry)]
    assert "changed_default.ban_on_hostile_signals" in kinds
    assert len(kinds) == len(set(kinds)) >= 2


def test_every_construction_warning_has_a_matching_problem() -> None:
    report = validate_config(
        {"trusted_proxies": ["0.0.0.0/0"], "nonsense_field": 1}, package="guard-core"
    )

    messages = strs(get(report, "construction_warnings"))
    problems = [
        text(get(e, "message")) for e in arr(get(report, "construction_problems"))
    ]

    assert messages == problems


def test_a_clean_config_has_no_problems_and_agent_package_works() -> None:
    report = validate_config({}, package="guard-agent")

    assert report["construction_problems"] == []
    assert report["construction_warnings"] == []


def test_a_record_without_kinds_gives_an_empty_kinds_list() -> None:
    plain = logging.LogRecord(
        "guard_core", logging.WARNING, "f", 1, "plain", None, None
    )

    assert config_module._record_kinds(plain) == []


@pytest.mark.parametrize(
    "attached",
    ["not-a-sequence", 7, [("only-one",)], [(1, "x")], [("kind", 3)]],
)
def test_malformed_kinds_are_ignored_or_given_no_subject(attached: object) -> None:
    record = logging.LogRecord("guard_core", logging.WARNING, "f", 1, "m", None, None)
    record.problems = attached

    kinds = config_module._record_kinds(record)

    assert kinds in ([], [{"kind": "kind", "subject": None}])


def test_module_loaders_cover_exactly_the_allowlisted_packages() -> None:
    assert set(config_module._MODULE_LOADERS) == set(PACKAGE_MODELS)
    for package, (module_name, _) in PACKAGE_MODELS.items():
        assert config_module._MODULE_LOADERS[package]().__name__ == module_name
