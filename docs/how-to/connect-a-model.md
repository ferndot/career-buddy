# Connect a model

Use this to let career-buddy read resumes with a language model and write resumes and letters. Writing documents needs a model. Importing works without one, using a rougher offline reader.

## Steps

1. Open **Settings** and choose **Add a connection**.
2. Pick a provider and fill in the address, model and key if it needs them. See the table.
3. Press **Test**. It asks the server for its model list. No resume text is sent and it costs nothing.
4. Press **Set active**.

Only one connection is active at a time, or none.

| Provider | Address | Key |
|---|---|---|
| Anthropic | `https://api.anthropic.com/v1` (fixed, native Messages API) | required |
| Google AI Studio | `https://generativelanguage.googleapis.com/v1beta/openai` (fixed) | required |
| Ollama | `http://localhost:11434/v1` | none |
| LM Studio | `http://localhost:1234/v1` | none |
| llama.cpp | `http://localhost:9931/v1` (its Docker image uses 8080) | optional |
| Custom URL | any OpenAI-compatible server | optional |

When career-buddy runs in Docker, `localhost` is the container. See [Run with Docker](run-with-docker.md#reach-a-model-on-your-computer).

## Where keys are stored

- In the OS keychain, through `keyring`.
- With no keychain, or with `CAREER_BUDDY_KEY_STORE=file` (the Docker image sets it), in `secrets.json` in the data folder. The file has mode 0600 but is plain text.
- Settings without keys are in `llm-settings.json`.
- The page and API only show a masked key such as `sk-...a1f2`. Keys are never logged.

## Rules to know

- Changing an address removes its saved key, so a key cannot be sent to a new host. Cloud addresses cannot be edited.
- Private addresses such as `192.168.x.x` show a warning and must be confirmed. Link-local and metadata addresses are refused.
- `CAREER_BUDDY_LLM_BASE_URL`, `CAREER_BUDDY_LLM_MODEL` and `CAREER_BUDDY_LLM_API_KEY` show up as a read-only connection named "From environment variables". It is active until you choose another or turn it off.

## API

`GET /api/llm/providers`, `GET|POST /api/llm/connections`, `PATCH|DELETE /api/llm/connections/{id}`, `PUT /api/llm/active`, `POST /api/llm/test`. Interactive documentation is at `/docs` on the running server.
