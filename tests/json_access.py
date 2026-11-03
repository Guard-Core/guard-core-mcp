from pydantic import TypeAdapter

from guard_core_mcp.json_types import JsonObject, JsonValue

_JSON_VALUE = TypeAdapter(JsonValue)


def parse_json(raw: str) -> JsonValue:
    return _JSON_VALUE.validate_json(raw)


def get(value: JsonValue, *path: str | int) -> JsonValue:
    """Walk a JSON value by key or index, failing the test on any shape mismatch."""
    for step in path:
        if isinstance(step, str):
            assert isinstance(value, dict), f"expected an object at {step!r}"
            value = value[step]
        else:
            assert isinstance(value, list), f"expected an array at index {step}"
            value = value[step]
    return value


def obj(value: JsonValue) -> JsonObject:
    assert isinstance(value, dict)
    return value


def arr(value: JsonValue) -> list[JsonValue]:
    assert isinstance(value, list)
    return value


def text(value: JsonValue) -> str:
    assert isinstance(value, str)
    return value


def strs(value: JsonValue) -> list[str]:
    items = arr(value)
    assert all(isinstance(item, str) for item in items)
    return [item for item in items if isinstance(item, str)]


def num(value: JsonValue) -> int | float:
    assert isinstance(value, int | float) and not isinstance(value, bool)
    return value
