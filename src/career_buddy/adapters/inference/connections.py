"""LLM connections: the saved list, one active choice, URL checks, and the connection test."""

from __future__ import annotations

import ipaddress
import json
import os
import secrets
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx

from career_buddy.adapters.inference.chat_graph import GraphCareerChat
from career_buddy.adapters.inference.chat_models import chat_model
from career_buddy.adapters.inference.writer_graph import GraphDocumentWriter
from career_buddy.adapters.inference.job_reviewer import ProviderJobReviewer
from career_buddy.adapters.inference.openai_compatible import openai_client
from career_buddy.adapters.inference.presets import BY_ID, PRESETS, Preset
from career_buddy.adapters.inference.probe import probe_anthropic, probe_openai
from career_buddy.adapters.inference.redstring_extractor import RedstringExtractor
from career_buddy.adapters.inference.rewriter import ProviderRewriter
from career_buddy.adapters.inference.structured_anthropic import StructuredAnthropicProvider, anthropic_client
from career_buddy.adapters.inference.structured_openai import StructuredOpenAIProvider
from career_buddy.adapters.storage.key_store import KeyStore

ENV_ID = "env"
LOCAL_NAMES = {"localhost", "host.docker.internal"}  # the Docker hint points here: it is this computer, not another one
REFUSED_NAMES = {"metadata.google.internal"}
KEEP = object()  # "leave the saved active choice as it is"


class InvalidConnection(ValueError):
    """The request cannot be saved. The message is plain words for the person using the page."""


@dataclass(frozen=True)
class Inference:
    """What the active connection provides, one provider behind each."""

    extractor: Any
    rewriter: Any
    writer: Any
    reviewer: Any
    chat: Any


class UnknownConnection(KeyError):
    pass


class ReadOnlyConnection(Exception):
    pass


@dataclass(frozen=True)
class Connection:
    id: str
    preset: str
    label: str
    base_url: str
    model: str
    key_hint: str | None = None
    allow_private: bool = False
    read_only: bool = False


def key_hint(key: str) -> str:
    return f"{key[:3]}...{key[-4:]}" if len(key) >= 12 else "...."


def _is_local(host: str) -> bool:
    if host in LOCAL_NAMES or host.endswith(".localhost"):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def check_url(url: str, allow_private: bool) -> str:
    # shortcut: host names are not resolved, so a name that points at a private address passes. Upgrade if URLs ever arrive from others.
    try:
        parts = urlsplit(url)
        host, _ = (parts.hostname or "").lower(), parts.port
    except ValueError as error:
        raise InvalidConnection("That address is not valid.") from error
    if parts.scheme not in ("http", "https") or not host:
        raise InvalidConnection("Enter a web address that starts with http:// or https://.")
    if parts.username or parts.password:
        raise InvalidConnection("Leave a name or password out of the address. Use the key field instead.")
    if host in REFUSED_NAMES:
        raise InvalidConnection("That address is not allowed.")
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return url
    if ip.is_link_local or ip.is_unspecified or ip.is_multicast:
        raise InvalidConnection("That address is not allowed.")
    if not ip.is_global and not ip.is_loopback and not allow_private:
        raise InvalidConnection("That address is on a private network. Confirm that you trust it to use it.")
    return url


class LLMConnections:
    def __init__(self, data_dir: Path, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._dir, self._file, self._transport = data_dir, data_dir / "llm-settings.json", transport
        self.keys = KeyStore(data_dir)

    # --- reading ---

    def _state(self) -> dict[str, Any]:
        return json.loads(self._file.read_text()) if self._file.exists() else {}

    def _saved(self) -> list[Connection]:
        return [Connection(**c) for c in self._state().get("connections", [])]

    def _env(self) -> Connection | None:
        url = os.environ.get("CAREER_BUDDY_LLM_BASE_URL")
        if not url:
            return None
        key = os.environ.get("CAREER_BUDDY_LLM_API_KEY", "")
        return Connection(ENV_ID, "custom", "From environment variables", url, os.environ.get("CAREER_BUDDY_LLM_MODEL", "default"),
                          key_hint(key) if key else None, True, True)

    def _all(self) -> list[Connection]:
        return [c for c in (self._env(), *self._saved()) if c]

    def _get(self, conn_id: str) -> Connection:
        found = next((c for c in self._all() if c.id == conn_id), None)
        if not found:
            raise UnknownConnection(conn_id)
        return found

    def _key(self, conn: Connection) -> str | None:
        return (os.environ.get("CAREER_BUDDY_LLM_API_KEY") or None) if conn.read_only else self.keys.get(conn.id)

    def active_id(self) -> str | None:
        state = self._state()
        wanted = state["active"] if "active" in state else (ENV_ID if self._env() else None)
        return wanted if any(c.id == wanted for c in self._all()) else None

    def providers(self) -> list[dict[str, object]]:
        return [p.to_json() for p in PRESETS]

    def view(self, conn: Connection) -> dict[str, Any]:
        host = (urlsplit(conn.base_url).hostname or "").lower()
        preset = BY_ID[conn.preset]
        return {**asdict(conn), "off_device": not _is_local(host), "destination": host if preset.url_editable else preset.label}

    def listing(self) -> dict[str, Any]:
        return {"active": self.active_id(), "connections": [self.view(c) for c in self._all()], "key_store": self.keys.kind}

    # --- writing ---

    def _write(self, connections: list[Connection], active: Any = KEEP) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        state = self._state() | {"connections": [asdict(c) for c in connections]}
        if active is not KEEP:
            state["active"] = active
        self._file.write_text(json.dumps(state, indent=2))

    def _resolve(self, preset_id: str | None, base_url: str | None, allow_private: bool) -> tuple[Preset, str]:
        preset = BY_ID.get(preset_id or "")
        if not preset:
            raise InvalidConnection("Choose one of the listed providers.")
        url = (base_url or preset.base_url).strip().rstrip("/") if preset.url_editable else preset.base_url
        if not url:
            raise InvalidConnection("Enter the server address.")
        return preset, check_url(url, allow_private)

    def create(self, fields: dict[str, Any]) -> dict[str, Any]:
        preset, url = self._resolve(fields.get("preset"), fields.get("base_url"), bool(fields.get("allow_private")))
        key = fields.get("api_key") or None
        if not (fields.get("model") or "").strip():
            raise InvalidConnection("Enter the model name to use.")
        if preset.needs_key and not key:
            raise InvalidConnection(f"{preset.label} needs an API key.")
        conn = Connection(secrets.token_hex(4), preset.id, (fields.get("label") or "").strip() or preset.label, url,
                          fields["model"].strip(), key_hint(key) if key else None, bool(fields.get("allow_private")))
        if key:
            self.keys.set(conn.id, key)
        self._write([*self._saved(), conn])
        return self.view(conn)

    def update(self, conn_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        conn = self._get(conn_id)
        if conn.read_only:
            raise ReadOnlyConnection(conn_id)
        if fields.get("preset", conn.preset) != conn.preset:
            raise InvalidConnection("The provider cannot be changed. Add a new connection instead.")
        if "base_url" in fields and not BY_ID[conn.preset].url_editable and fields["base_url"] != conn.base_url:
            raise InvalidConnection(f"The {conn.label} address is fixed and cannot be changed.")
        allow = bool(fields.get("allow_private", conn.allow_private))
        _, url = self._resolve(conn.preset, fields.get("base_url", conn.base_url), allow)
        if fields.get("model") is not None and not fields["model"].strip():
            raise InvalidConnection("Enter the model name to use.")
        updated = replace(conn, base_url=url, allow_private=allow, label=(fields.get("label") or conn.label).strip(),
                          model=(fields.get("model") or conn.model).strip())
        if url != conn.base_url:  # a saved key must never follow the URL to a new host
            self.keys.delete(conn.id)
            updated = replace(updated, key_hint=None)
        if fields.get("api_key"):
            self.keys.set(conn.id, fields["api_key"])
            updated = replace(updated, key_hint=key_hint(fields["api_key"]))
        self._write([updated if c.id == conn_id else c for c in self._saved()])
        return self.view(updated)

    def delete(self, conn_id: str) -> None:
        if self._get(conn_id).read_only:
            raise ReadOnlyConnection(conn_id)
        self.keys.delete(conn_id)
        self._write([c for c in self._saved() if c.id != conn_id], None if self.active_id() == conn_id else KEEP)

    def set_active(self, conn_id: str | None) -> str | None:
        if conn_id is not None:
            self._get(conn_id)
        self._write(self._saved(), conn_id)
        return conn_id

    # --- using ---

    def _client(self, conn: Connection, key: str | None) -> httpx.AsyncClient:
        if conn.preset == "anthropic":
            return anthropic_client(key or "", self._transport, conn.base_url)
        return openai_client(conn.base_url, key or "", self._transport)

    def inference(self) -> Inference | None:
        """The extractor, rewriter, document writer, job reviewer and career chat for the active connection, or None so the caller uses the offline
        heuristics. All go through one LlmProvider, whichever API the connection speaks."""
        conn = next((c for c in self._all() if c.id == self.active_id()), None)
        if not conn:
            return None
        key = self._key(conn)
        client = self._client(conn, key)
        provider = (StructuredAnthropicProvider(client, conn.model) if conn.preset == "anthropic"
                    else StructuredOpenAIProvider(client, conn.model))
        chat = chat_model(conn.preset, conn.base_url, conn.model, key, self._transport)
        return Inference(RedstringExtractor(provider), ProviderRewriter(provider), GraphDocumentWriter(chat), ProviderJobReviewer(provider), GraphCareerChat(chat))

    async def test(self, conn_id: str | None, draft: dict[str, Any]) -> dict[str, Any]:
        """Ask the server for its model list. No resume text is sent and nothing is billed."""
        if conn_id:
            conn = self._get(conn_id)
            key = self._key(conn)
        else:
            preset, url = self._resolve(draft.get("preset"), draft.get("base_url"), bool(draft.get("allow_private")))
            conn, key = Connection("draft", preset.id, preset.label, url, draft.get("model") or "default"), draft.get("api_key") or None
        client = self._client(conn, key)
        try:
            models = await (probe_anthropic(client) if conn.preset == "anthropic" else probe_openai(client, conn.model))
        except httpx.HTTPStatusError as error:
            code = error.response.status_code
            reason = "The server refused the key. Check it and try again." if code in (401, 403) else f"The server answered with an error (status {code})."
            return {"ok": False, "message": reason, "models": []}
        except httpx.HTTPError:
            return {"ok": False, "message": f"Could not reach {urlsplit(conn.base_url).hostname}. Is it running?", "models": []}
        except (KeyError, TypeError, ValueError):
            return {"ok": False, "message": "The server answered, but not with a list of models.", "models": []}
        finally:
            await client.aclose()
        found = f"{len(models)} models available" if models else "The server answered"
        return {"ok": True, "message": f"Connected. {found}.", "models": models}
