# Configuration

career-buddy reads these environment variables. All are optional unless a row says otherwise.

## Server

| Variable | Default | Meaning |
|---|---|---|
| `HOST` | `127.0.0.1` | Address the server binds to. The Docker image sets `0.0.0.0`. |
| `PORT` | `8000` | Port the server listens on. |
| `RELOAD` | unset | `1` restarts the server when a source file changes. Development only. It also stops the browser from opening. |
| `CAREER_BUDDY_NO_BROWSER` | unset | `1` stops the app from opening your browser at start. |
| `CAREER_BUDDY_ALLOWED_HOSTS` | unset | Comma-separated host names accepted besides `localhost` and `127.0.0.1`. Other `Host` headers are refused. |
| `CAREER_BUDDY_CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated origins allowed to call the API. |
| `CAREER_BUDDY_LOG_LEVEL` | `INFO` | Level for the `career_buddy` loggers. |

## Data and keys

| Variable | Default | Meaning |
|---|---|---|
| `CAREER_BUDDY_DATA` | per OS, see below | Folder for the event log, settings and stored files. |
| `CAREER_BUDDY_KEY_STORE` | unset | `file` keeps API keys in `secrets.json` in the data folder instead of the OS keychain. |

Default data folder:

- Windows: `%LOCALAPPDATA%\career-buddy`
- macOS: `~/Library/Application Support/career-buddy`
- Linux: `$XDG_DATA_HOME/career-buddy`, or `~/.local/share/career-buddy`

## Model

| Variable | Meaning |
|---|---|
| `CAREER_BUDDY_LLM_BASE_URL` | Address of an OpenAI-compatible server. Setting it adds a read-only connection. |
| `CAREER_BUDDY_LLM_MODEL` | Model name for that connection. |
| `CAREER_BUDDY_LLM_API_KEY` | Key for that connection. |

See [Connect a model](../how-to/connect-a-model.md).

## Storage

| Variable | Default | Meaning |
|---|---|---|
| `CAREER_BUDDY_STORAGE` | `local` | `local` or `s3`. |
| `CAREER_BUDDY_S3_ENDPOINT` | none | Required when storage is `s3`. |
| `CAREER_BUDDY_S3_BUCKET` | none | Required when storage is `s3`. |
| `CAREER_BUDDY_S3_ACCESS_KEY` | none | Required when storage is `s3`. |
| `CAREER_BUDDY_S3_SECRET_KEY` | none | Required when storage is `s3`. |
| `CAREER_BUDDY_S3_REGION` | `us-east-1` | Region for the S3 client. |

See [Store originals in S3](../how-to/store-originals-in-s3.md).

## Frontend

| Variable | Default | Meaning |
|---|---|---|
| `API_TARGET` | `http://127.0.0.1:8000` | Where `pnpm -C frontend dev` forwards `/api`. |
| `VITE_API_URL` | unset | Call this backend directly instead of using the dev proxy. The backend must list the page origin in `CAREER_BUDDY_CORS_ORIGINS`. |

## Tests

| Variable | Meaning |
|---|---|
| `CAREER_BUDDY_LIVE_ANTHROPIC_KEY`, `CAREER_BUDDY_LIVE_GEMINI_KEY` | Turn on the live model tests in `tests/test_llm_live.py`. |
