"""The tool-calling chat model of a connection, for the document writer. Every preset goes through the OpenAI-compatible API, Anthropic's included
(its own client cannot take the injected transport that keeps the tests offline and redirects off)."""

from __future__ import annotations

import httpx
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from career_buddy.adapters.inference.openai_compatible import openai_client


def chat_model(preset: str, base_url: str, model: str, key: str | None, transport: httpx.AsyncBaseTransport | None = None) -> BaseChatModel:
    """No retries: a failed call is the caller's to handle. Anthropic rejects `temperature: 0` on some models, so it is left to the server there."""
    return ChatOpenAI(model=model, base_url=base_url, api_key=key or "none", max_retries=0,  # type: ignore[arg-type]
                      **({} if preset == "anthropic" else {"temperature": 0}),
                      http_async_client=openai_client(base_url, key or "", transport))
