---
title: LLM connections settings, design decisions
status: Shaped
created: 2026-11-15
extends: plan-v2
---

# LLM connections: decisions

Endpoints checked against official docs on 2026-11-15.

## L1. Providers and adapters

| Preset | Adapter | Base URL | Auth | Limits |
|---|---|---|---|---|
| Anthropic | **new** `inference/anthropic.py` | `https://api.anthropic.com/v1` | `x-api-key`, `anthropic-version` | Omit `temperature` (Claude 4.7+ rejects values below 1) |
| Gemini | existing OpenAI-compatible | `https://generativelanguage.googleapis.com/v1beta/openai` | Bearer | Beta layer |
| Ollama | existing | `http://localhost:11434/v1` | none | |
| LM Studio | existing | `http://localhost:1234/v1` | none | |
| llama.cpp | existing | `http://localhost:9931/v1` | optional Bearer | |
| Custom | existing | user-entered | optional Bearer | |

- **Native Anthropic:** Anthropic says its OpenAI layer is not production-ready, and that layer rejects our `temperature: 0`.
- **Gemini through its OpenAI layer:** only the URL changes, and the key goes in a header, not the URL.
- **llama.cpp on 9931:** that is the current default port. The hint says "8080 for the Docker image".

## L2. Presets

Each preset has `id, label, base_url, url_editable, needs_key, off_device, hint`. Only local and custom URLs can be edited, so a cloud key cannot go elsewhere.

## L3. Key storage

- **Primary: OS keychain** (`keyring`, MIT). It encrypts keys at rest.
- **Fallback: `<data>/secrets.json`, mode 0600.** Used when `CAREER_GRAPH_KEY_STORE=file` or there is no keychain.
- **Plain text:** `<data>/llm-settings.json` holds the connections and active id. The fallback file holds keys in plain text, and the UI says so.
- **Env vars:** `CAREER_GRAPH_LLM_*` shows up as a read-only connection, so the existing setup keeps working.

## L4. Security

- **Masked keys:** responses carry only `key_hint` (`sk-...a1f2`). A Hypothesis test checks this.
- **No key in logs:** provider error bodies are dropped, and `LLMUnavailable` carries only the status code.
- **URL change clears the key:** a saved key cannot be sent to a new host.
- **Base URL only:** redirects are not followed (the httpx default).
- **URL check:** http and https only. Link-local (metadata) addresses are refused, and private addresses need `allow_private: true` after a warning.
- **Localhost only:** `TrustedHostMiddleware` blocks DNS rebinding.
- **Data badge:** each card says "Resume text is sent to Anthropic" or "Stays on this computer".

## L5. Selection

One active connection or none, with an "Active" label. With none, the heuristic extractor runs and suggestions are hidden. Changing the active connection rebuilds `App`.

## L6. API

| Method and path | Body |
|---|---|
| `GET /api/llm/providers` | none |
| `GET /api/llm/connections` | none. Returns `{active, connections}`, masked. |
| `POST /api/llm/connections` | `{preset, label?, base_url?, model, api_key?, allow_private?}` |
| `PATCH /api/llm/connections/{id}` | the same fields, all optional |
| `DELETE /api/llm/connections/{id}` | none. Removes the key. |
| `PUT /api/llm/active` | `{id: str \| null}` |
| `POST /api/llm/test` | `{id}` or an unsaved draft. Returns `{ok, message, models}`. |

**Test:** sends `GET {base}/models`. It sends no resume text, costs no tokens and fills the model list. On 404 it sends a one-token chat message instead.

## L7. Tests

- One `httpx.MockTransport` test per adapter, covering URL, headers, body and error mapping.
- `create_app(llm_client=)` becomes `llm_transport=`, so `conftest.py` and `test_tailoring_api.py` change too.
- Tests use `CAREER_GRAPH_KEY_STORE=file` in `tmp_path`.
- `@pytest.mark.live` tests are skipped unless `CAREER_GRAPH_LIVE_<PROVIDER>_KEY` is set.

## L8. Docker

- The image sets `CAREER_GRAPH_KEY_STORE=file`. Settings and keys live in `/data` (`./data` on the host).
- The local hints suggest `host.docker.internal`, and compose adds `extra_hosts: host-gateway` so it works on Linux.
