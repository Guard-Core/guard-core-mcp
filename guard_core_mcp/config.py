import difflib
import importlib
import importlib.metadata
import logging
import threading
import typing
import warnings
from collections.abc import Callable
from types import ModuleType

from pydantic import BaseModel, ValidationError
from pydantic.fields import FieldInfo, PydanticUndefined

from guard_core_mcp.json_types import JsonObject, JsonValue

PACKAGE_MODELS: dict[str, tuple[str, str]] = {
    "guard-core": ("guard_core", "SecurityConfig"),
    "fastapi-guard": ("guard", "SecurityConfig"),
    "guard-agent": ("guard_agent", "AgentConfig"),
}

# One loader per package, each importing a literal module name, so the import is
# visible to static analysis and no package string is ever used as a module name.
_MODULE_LOADERS: dict[str, Callable[[], ModuleType]] = {
    "guard-core": lambda: importlib.import_module("guard_core"),
    "fastapi-guard": lambda: importlib.import_module("guard"),
    "guard-agent": lambda: importlib.import_module("guard_agent"),
}


def resolve_model(package: str) -> tuple[type[BaseModel], str | None]:
    if package not in PACKAGE_MODELS:
        raise ValueError(
            f"unknown package {package!r}; expected one of {', '.join(PACKAGE_MODELS)}"
        )
    _, attribute = PACKAGE_MODELS[package]
    module = _MODULE_LOADERS[package]()
    model: type[BaseModel] = getattr(module, attribute)
    try:
        version: str | None = importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        version = None
    return model, version


def _format_annotation(annotation: object) -> str:
    origin = typing.get_origin(annotation)
    args = typing.get_args(annotation)

    if origin is None:
        name = getattr(annotation, "__name__", None)
        if name is not None:
            return str(name)
        return str(annotation).replace("typing.", "")

    origin_name = getattr(origin, "__name__", None) or str(origin).replace(
        "typing.", ""
    )
    if not args:
        return origin_name

    formatted_args = ", ".join(_format_annotation(argument) for argument in args)
    return f"{origin_name}[{formatted_args}]"


def _serialize_default(default: object) -> str | None:
    if default is PydanticUndefined or default is None:
        return None
    return repr(default)


def describe_field(name: str, info: FieldInfo) -> JsonObject:
    return {
        "name": name,
        "type": _format_annotation(info.annotation),
        "default": _serialize_default(info.default),
        "required": info.is_required(),
        "description": info.description,
    }


def _deprecation_entry(message: str, known_fields: set[str]) -> JsonObject:
    first_token = message.split(maxsplit=1)[0]
    return {
        "field": first_token if first_token in known_fields else None,
        "message": message,
    }


class _ConstructionWarningCapture(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)

    def _deduped(self) -> list[logging.LogRecord]:
        seen: set[str] = set()
        deduped: list[logging.LogRecord] = []
        for record in self.records:
            message = record.getMessage()
            if message in seen:
                continue
            seen.add(message)
            deduped.append(record)
        return deduped

    def messages(self) -> list[str]:
        return [record.getMessage() for record in self._deduped()]

    def problems(self) -> list[JsonValue]:
        return [
            {"message": record.getMessage(), "kinds": _record_kinds(record)}
            for record in self._deduped()
        ]


def _record_kinds(record: logging.LogRecord) -> list[JsonValue]:
    """The misconfiguration kinds guard-core attaches to a log record.

    guard-core 5.x puts ``problems=((kind, subject), ...)`` in the record's extra;
    an older engine, or a record that is not a misconfiguration, has none.
    """
    attached: object = getattr(record, "problems", ())
    if not isinstance(attached, (tuple, list)):
        return []
    kinds: list[JsonValue] = []
    for item in attached:
        if isinstance(item, (tuple, list)) and len(item) == 2:
            kind, subject = item
            if isinstance(kind, str):
                kinds.append(
                    {
                        "kind": kind,
                        "subject": subject if isinstance(subject, str) else None,
                    }
                )
    return kinds


_guard_core_logger_lock = threading.Lock()


def parse_validation_error(exception: ValidationError) -> list[JsonValue]:
    return [
        {
            "field": ".".join(str(part) for part in error["loc"]),
            "message": error["msg"],
            "input": repr(error.get("input")),
        }
        for error in exception.errors()
    ]


def _retry_without_rejected_fields(
    model: type[BaseModel], config: JsonObject, exception: ValidationError
) -> None:
    rejected = {
        str(error["loc"][0]) for error in exception.errors() if error.get("loc")
    }
    remaining = {key: value for key, value in config.items() if key not in rejected}
    try:
        model(**remaining)
    except ValidationError:
        pass


def validate_config(config: JsonObject, package: str = "fastapi-guard") -> JsonObject:
    model, version = resolve_model(package)
    known_fields = set(model.model_fields)

    unknown_fields: list[JsonValue] = [
        {
            "name": key,
            "did_you_mean": [
                *difflib.get_close_matches(key, known_fields, n=3, cutoff=0.75)
            ],
        }
        for key in config
        if key not in known_fields
    ]

    errors: list[JsonValue] = []
    guard_core_logger = logging.getLogger("guard_core")
    capture = _ConstructionWarningCapture()
    with _guard_core_logger_lock:
        original_level = guard_core_logger.level
        guard_core_logger.addHandler(capture)
        guard_core_logger.setLevel(logging.WARNING)
        try:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                try:
                    model(**config)
                except ValidationError as exception:
                    errors = parse_validation_error(exception)
                    _retry_without_rejected_fields(model, config, exception)
        finally:
            guard_core_logger.removeHandler(capture)
            guard_core_logger.setLevel(original_level)

    deprecated: list[JsonValue] = []
    reported: set[str] = set()
    for warning in caught:
        if not issubclass(warning.category, DeprecationWarning):
            continue
        message = str(warning.message)
        if message in reported:
            continue
        reported.add(message)
        deprecated.append(_deprecation_entry(message, known_fields))

    return {
        "valid": not errors and not unknown_fields,
        "package": package,
        "version": version,
        "model": model.__name__,
        "errors": errors,
        "unknown_fields": unknown_fields,
        "deprecated": deprecated,
        "construction_warnings": [*capture.messages()],
        "construction_problems": capture.problems(),
    }


def config_fields(query: str, package: str = "fastapi-guard") -> JsonObject:
    model, version = resolve_model(package)
    fields = model.model_fields

    exact = describe_field(query, fields[query]) if query in fields else None

    tokens = query.lower().split()
    matches: list[JsonValue] = [
        describe_field(name, info)
        for name, info in fields.items()
        if name != query
        and all(token in f"{name} {info.description or ''}".lower() for token in tokens)
    ]

    if not matches and exact is None:
        matches = [
            describe_field(name, fields[name])
            for name in difflib.get_close_matches(query, list(fields), n=5)
        ]

    return {
        "package": package,
        "version": version,
        "query": query,
        "exact": exact,
        "matches": matches,
    }
