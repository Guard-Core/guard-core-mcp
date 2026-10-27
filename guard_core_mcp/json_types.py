from typing import Annotated

from pydantic import BaseModel, TypeAdapter, WithJsonSchema
from pydantic import JsonValue as _PydanticJsonValue

# The empty schema keeps the published tool schemas identical to the former
# dict[str, Any]: any JSON value is accepted.
JsonValue = Annotated[_PydanticJsonValue, WithJsonSchema({})]
JsonObject = dict[str, JsonValue]

_JSON_OBJECT = TypeAdapter(JsonObject)


def dump_json_object(model: BaseModel) -> JsonObject:
    return _JSON_OBJECT.validate_python(model.model_dump())
