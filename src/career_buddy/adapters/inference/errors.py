"""Maps provider failures to `LLMUnavailable`. The message carries the status code only: never a body, URL or key.
The log carries a little more (a short body preview), because that is what explains a refused call."""

from __future__ import annotations

import logging

import httpx

from career_buddy.application.ports import LLMUnavailable

log = logging.getLogger("career_buddy.extraction.provider")
CAUGHT = (httpx.HTTPError, AttributeError, KeyError, IndexError, TypeError, ValueError)


def unavailable(error: Exception) -> LLMUnavailable:
    if isinstance(error, httpx.HTTPStatusError):
        log.warning("the model server answered %d: %r", error.response.status_code, error.response.text[:300])
        return LLMUnavailable(f"The model server answered with status {error.response.status_code}")
    if isinstance(error, httpx.HTTPError):
        log.warning("the model server could not be reached: %s", type(error).__name__)
        return LLMUnavailable("The model server could not be reached")
    log.warning("the model server's answer could not be read: %s: %s", type(error).__name__, error)
    return LLMUnavailable("The model server sent an answer this app could not read")
