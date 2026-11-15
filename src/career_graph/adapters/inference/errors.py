"""Maps provider failures to `LLMUnavailable`. The message carries the status code only: never a body, URL or key."""

from __future__ import annotations

import httpx

from career_graph.application.ports import LLMUnavailable

CAUGHT = (httpx.HTTPError, AttributeError, KeyError, IndexError, TypeError, ValueError)


def unavailable(error: Exception) -> LLMUnavailable:
    if isinstance(error, httpx.HTTPStatusError):
        return LLMUnavailable(f"The model server answered with status {error.response.status_code}")
    if isinstance(error, httpx.HTTPError):
        return LLMUnavailable("The model server could not be reached")
    return LLMUnavailable("The model server sent an answer this app could not read")
