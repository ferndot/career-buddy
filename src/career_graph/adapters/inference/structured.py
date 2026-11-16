"""Shared by every LLM provider: ask for one JSON object, read it back, validate it against a pydantic schema."""

from __future__ import annotations

import json

from pydantic import BaseModel, ValidationError
from redstring import MalformedCompletionError


def instructions(system_prompt: str | None, schema: type[BaseModel]) -> str:
    """The caller's system prompt, plus the one JSON Schema the answer must match."""
    return (f"{system_prompt or ''}\n\nReply with one JSON object that matches this JSON Schema, and nothing else:\n"
            + json.dumps(schema.model_json_schema()))


def read_reply[S: BaseModel](reply: str, schema: type[S], model: str) -> S:
    """Validate the reply. Tolerates text or a code fence around the object; anything else raises MalformedCompletionError."""
    try:
        return schema.model_validate_json(reply[reply.index("{"): reply.rindex("}") + 1])
    except (ValidationError, ValueError) as error:
        raise MalformedCompletionError(model=model, schema=schema.__name__, cause=type(error).__name__) from error
