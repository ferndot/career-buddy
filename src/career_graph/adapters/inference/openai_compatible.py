"""The OpenAI-compatible HTTP client. Every OpenAI-compatible connection builds its provider on this."""

from __future__ import annotations

import httpx


def openai_client(base_url: str, api_key: str = "", transport: httpx.AsyncBaseTransport | None = None) -> httpx.AsyncClient:
    """A client rooted at the server's base URL. The key goes in a header, never the URL. Redirects are not followed."""
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    return httpx.AsyncClient(base_url=base_url.rstrip("/") + "/", headers=headers, transport=transport, timeout=120)
