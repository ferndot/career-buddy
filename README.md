# career-buddy

career-buddy keeps your career history as a graph of facts: positions, achievements, skills and education. You import a resume (a PDF, DOCX, TXT or MD file, or pasted text), review and edit the facts, then build a resume or cover letter for a job posting. A language model writes the text, and every sentence must cite your facts. Your data stays on your computer.

## Quick start

You need [Docker](https://docs.docker.com/get-docker/) running. From the project folder:

```bash
docker compose up --build -d
```

Open http://localhost:8080. To stop it:

```bash
docker compose down
```

Your data is kept in `./data`, so it survives rebuilds. On macOS and Linux, `make` does the same as the first command, `make stop` stops it and `make logs` follows the log. More in [Run with Docker](docs/how-to/run-with-docker.md).

No Docker? Follow the setup below.

## Prerequisites

| Tool | Version | Used for |
|---|---|---|
| [uv](https://docs.astral.sh/uv/) | 0.13 or newer (tested with 0.13.6) | Python packages and running the app. It also downloads Python 3.13 for you if you have none. |
| Python | 3.13 (set in `.python-version`) | The backend. You do not need to install it yourself. |
| [Node.js](https://nodejs.org/) | 24 LTS. 22.22.2 or newer also works. | Building the web UI and running its tests. |
| [pnpm](https://pnpm.io/installation) | 12.16.1 | The frontend package manager. |
| Chromium | Installed by a project command (about 150 MB) | PDF output only. You do not need it to import a resume or to download DOCX, TXT, Markdown or HTML. |
| Git | Any recent version | Getting the code. |

## Setup

Run each command from the project folder. The commands are the same on Windows, macOS and Linux unless a block says otherwise.

### 1. Get the code

```bash
git clone https://github.com/ferndot/career-buddy.git
```

```bash
cd career-buddy
```

### 2. Install uv

Windows (PowerShell):

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

macOS and Linux:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Close the terminal and open a new one, then check it:

```bash
uv --version
```

### 3. Install Node.js and pnpm

Install Node.js 24 LTS from [nodejs.org](https://nodejs.org/) (any OS), or with your package manager. Then:

```bash
npm install -g pnpm@12.16.1
```

```bash
pnpm --version
```

### 4. Install the Python packages

```bash
uv sync
```

### 5. Install Chromium for PDF output

```bash
uv run career-buddy install-browser
```

### 6. Build the web UI

```bash
pnpm -C frontend install
```

```bash
pnpm -C frontend build
```

The build writes the UI into `src/career_buddy/web/static`. The backend serves it from there.

## Run the app

```bash
uv run career-buddy
```

This starts the server at http://127.0.0.1:8000 and opens it in your browser. Stop it with Ctrl+C. API documentation is at http://127.0.0.1:8000/docs.

Your data goes to a folder for your OS: `%LOCALAPPDATA%\career-buddy` on Windows, `~/Library/Application Support/career-buddy` on macOS, and `~/.local/share/career-buddy` on Linux. Set `CAREER_BUDDY_DATA` to use another folder. See [Configuration](docs/reference/configuration.md).

### Run for development

To edit the UI with hot reload, use two terminals. In the first, start the backend:

```bash
uv run career-buddy
```

In the second, start the frontend:

```bash
pnpm -C frontend dev
```

Open http://localhost:5173. It forwards `/api` requests to the backend on port 8000.

## Run the tests

Backend:

```bash
uv run pytest -q
```

Frontend:

```bash
pnpm -C frontend test
```

Tests that call a real model (marked `live`) and the S3 test skip themselves unless you set their environment variables, so 3 skipped tests is normal. PDF tests skip until you install Chromium (step 5). One test is a known failure at the moment: `tests/test_split_skills.py::test_no_skill_is_empty_or_holds_a_top_level_separator`. Everything else should pass. More in [Run the tests](docs/how-to/run-the-tests.md).

## Troubleshooting

**`uv` is not recognized or `command not found`.** Open a new terminal. If it still fails, add the uv folder to your PATH: `%USERPROFILE%\.local\bin` on Windows, `~/.local/bin` on macOS and Linux.

**PowerShell says `pnpm.ps1 cannot be loaded because running scripts is disabled`.** Allow local scripts for your user, then open a new terminal:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

You never need to activate a virtual environment. Always start Python tools with `uv run`.

**PDF download fails with `Chromium is not installed`.** Run `uv run career-buddy install-browser`. On Linux, if Chromium starts but reports missing libraries, run `uv run playwright install-deps chromium` (it asks for sudo).

**The page at port 8000 shows JSON or a 404, not the app.** The UI is not built. Run `pnpm -C frontend build` (step 6).

**Port already in use.** Pick another port. On macOS and Linux:

```bash
PORT=8001 uv run career-buddy
```

On Windows (PowerShell):

```powershell
$env:PORT = "8001"; uv run career-buddy
```

If you also run `pnpm -C frontend dev`, point it at the new port with `API_TARGET=http://127.0.0.1:8001` (PowerShell: `$env:API_TARGET = "http://127.0.0.1:8001"`).

**`Invalid host header`.** The server only answers `localhost` and `127.0.0.1`. Add other names to `CAREER_BUDDY_ALLOWED_HOSTS`.

**A resume gives few facts, or documents cannot be written.** Without a model, only the offline reader runs, and writing resumes and letters needs a model. See [Connect a model](docs/how-to/connect-a-model.md).

## More documentation

- [Getting started](docs/tutorials/01-getting-started.md): the full walkthrough, from install to a downloaded resume.
- [How-to guides](docs/index.md#how-to-guides): Docker, development servers, tests, models, S3 storage.
- [Reference](docs/index.md#reference): configuration, the `career-buddy` command, the HTTP API.
- [Architecture](docs/explanation/architecture.md): how the code is organized.
- [Contributing](docs/contributing.md): the rules for code and docs, including the 500-line file limit.

## License

Apache-2.0. See [LICENSE](LICENSE). Dependencies are permissive: FastAPI (MIT), uvicorn (BSD), httpx (BSD), keyring (MIT), python-multipart (Apache-2.0), Playwright (Apache-2.0), pdfminer.six (MIT), python-docx (MIT), boto3 (Apache-2.0). The optional S3 server runs apart and is reached over the S3 API only.
