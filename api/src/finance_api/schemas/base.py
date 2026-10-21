from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """Base for models exchanged with the TypeScript frontend: snake_case in Python,
    camelCase in JSON (`tool_call_id` <-> `toolCallId`)."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_name=True,  # build with Python names: Quote(change_percent=...)
        validate_by_alias=True,  # or parse JSON names: {"changePercent": ...}
        serialize_by_alias=True,  # model_dump() / JSON output uses camelCase
    )
