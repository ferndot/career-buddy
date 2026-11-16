"""Shared by every LLM provider: ask for one JSON object, read it back, validate it against a pydantic schema."""

from __future__ import annotations

import json
import logging

from pydantic import BaseModel, ValidationError
from redstring import MalformedCompletionError

log = logging.getLogger("career_graph.extraction.reply")


def instructions(system_prompt: str | None, schema: type[BaseModel]) -> str:
    """The caller's system prompt, plus the one JSON Schema the answer must match."""
    return (f"{system_prompt or ''}\n\nReply with one JSON object that matches this JSON Schema, and nothing else:\n"
            + json.dumps(schema.model_json_schema()))


def warn_if_cut_off(model: str, reason: str | None, cut_off_reason: str, reply: str) -> None:
    """A reply that stopped at the output limit is cut mid-object, so it will not read back as JSON."""
    if reason == cut_off_reason:
        log.warning("[%s] the reply stopped at the output limit (%s) after %d characters; it is probably cut off",
                    model, reason, len(reply))


def _malformed(reply: str, schema: type[BaseModel], model: str, cause: str) -> MalformedCompletionError:
    log.warning("[%s] the reply is not a valid %s (%s). First 300 characters: %r", model, schema.__name__, cause, reply[:300])
    return MalformedCompletionError(model=model, schema=schema.__name__, cause=cause)


def read_reply[S: BaseModel](reply: str, schema: type[S], model: str) -> S:
    """Validate the reply. Tolerates text or a code fence around the object; anything else raises MalformedCompletionError.
    The schema's required keys must be present: pydantic alone would read `{}`, or an object of the wrong shape,
    as "found nothing", which looks exactly like a document with nothing in it."""
    try:
        data = json.loads(reply[reply.index("{"): reply.rindex("}") + 1])
    except ValueError as error:  # no braces, or not JSON
        raise _malformed(reply, schema, model, type(error).__name__) from error
    if missing := [k for k in schema.model_json_schema().get("required", ()) if k not in data]:
        raise _malformed(reply, schema, model, "missing " + ", ".join(missing))
    try:
        return schema.model_validate(data)
    except ValidationError as error:
        raise _malformed(reply, schema, model, type(error).__name__) from error
