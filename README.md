# career-buddy

career-buddy keeps your career history as a graph of facts: positions, achievements, skills and education. You import a resume (a PDF, DOCX, TXT or MD file, or pasted text), review and edit the facts, then build a resume or cover letter for a job posting. A language model writes the text, and every sentence must cite your facts. Your data stays on your computer.

## Install and run

You do not need to know how to code. You need Docker Desktop and a terminal (PowerShell on Windows, Terminal on macOS).

1. Install [Docker Desktop](https://docs.docker.com/get-docker/) and start it. Wait until it says Docker is running.

2. Download the code. Open https://github.com/ferndot/career-buddy, choose **Code**, then **Download ZIP**, and unzip it. Open a terminal in the unzipped folder. On Windows, open the folder in File Explorer, right-click an empty space and choose **Open in Terminal**. If you have Git, you can run these two commands instead:

   ```bash
   git clone https://github.com/ferndot/career-buddy.git
   ```

   ```bash
   cd career-buddy
   ```

3. Start the app. The first run builds it and takes a few minutes.

   ```bash
   docker compose up --build -d
   ```

   If you have `make` (macOS, Linux, or Windows with it installed), `make run` does the same thing.

4. Open http://localhost:8080 in your browser.

To stop it:

```bash
docker compose down
```

With `make`, use `make stop` to stop, and `make logs` to follow the logs.

Your data is kept in the `data` folder next to the code, so it survives restarts and rebuilds. To write resumes and letters you also need to connect a language model: see [Connect a model](docs/how-to/connect-a-model.md). For a walkthrough from import to a downloaded resume, see [Getting started](docs/tutorials/01-getting-started.md). More on Docker: [Run with Docker](docs/how-to/run-with-docker.md).

## For developers

Everything below is for people who change the code. You do not need it to use the app. [Getting started](docs/tutorials/01-getting-started.md) walks through this setup step by step.

### Prerequisites

| Tool | Version | Used for |
|---|---|---|
| [uv](https://docs.astral.sh/uv/) | 0.13 or newer (tested with 0.13.6) | Python packages and running the app. It also downloads Python 3.13 for you if you have none. |
| Python | 3.13 (set in `.python-version`) | The backend. You do not need to install it yourself. |
| [Node.js](https://nodejs.org/) | 24 LTS. 22.22.2 or newer also works. | Building the web UI and running its tests. |
| [pnpm](https://pnpm.io/installation) | 12.16.1 | The frontend package manager. |
| Chromium | Installed by a project command (about 150 MB) | PDF output only. You do not need it to import a resume or to download DOCX, TXT, Markdown or HTML. |
| Git | Any recent version | Getting the code. |

### Setup

Run each command from the project folder. The commands are the same on Windows, macOS and Linux unless a block says otherwise.

1. Get the code:

   ```bash
   git clone https://github.com/ferndot/career-buddy.git
   ```

   ```bash
   cd career-buddy
   ```

2. Install uv. Windows (PowerShell):

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

3. Install Node.js 24 LTS from [nodejs.org](https://nodejs.org/), then pnpm:

   ```bash
   npm install -g pnpm@12.16.1
   ```

   ```bash
   pnpm --version
   ```

4. Install the Python packages:

   ```bash
   uv sync
   ```

5. Install Chromium for PDF output:

   ```bash
   uv run career-buddy install-browser
   ```

6. Build the web UI. It is written into `src/career_buddy/web/static`, and the backend serves it from there:

   ```bash
   pnpm -C frontend install
   ```

   ```bash
   pnpm -C frontend build
   ```

### Run the app

```bash
uv run career-buddy
```

This starts the server at http://127.0.0.1:8000 and opens it in your browser. Stop it with Ctrl+C. API documentation is at http://127.0.0.1:8000/docs. The command has no `--help`: any option you pass is ignored and the server starts. Its only subcommand is `install-browser`. See [the command reference](docs/reference/career-buddy-cli.md).

Your data goes to a folder for your OS: `%LOCALAPPDATA%\career-buddy` on Windows, `~/Library/Application Support/career-buddy` on macOS, and `~/.local/share/career-buddy` on Linux. Set `CAREER_BUDDY_DATA` to use another folder. See [Configuration](docs/reference/configuration.md).

To edit the UI with hot reload, use two terminals. In the first, start the backend:

```bash
uv run career-buddy
```

In the second, start the frontend, then open http://localhost:5173. It forwards `/api` requests to the backend on port 8000.

```bash
pnpm -C frontend dev
```

### Run the tests

Backend:

```bash
uv run pytest -q
```

Frontend:

```bash
pnpm -C frontend test
```

Tests that call a real model (marked `live`) and the S3 test skip themselves unless you set their environment variables, so 3 skipped tests is normal. PDF tests skip until you install Chromium (setup step 5). One test is a known failure at the moment: `tests/test_split_skills.py::test_no_skill_is_empty_or_holds_a_top_level_separator`. Everything else should pass. More in [Run the tests](docs/how-to/run-the-tests.md).

## Developer tools

The project is managed with `spec-ops`, the SpecOps project-management CLI. It is used by `uv run spec-ops health` (file-length check) and `uv run spec-ops docs audit` (documentation check). It is not part of this repo's `uv sync`, so install it once from its own repository:

```bash
uv tool install git+https://github.com/tyevans/spec-ops
```

Then run it from the project folder with `uv run spec-ops health` and `uv run spec-ops docs audit`. On Windows, set `PYTHONIOENCODING=utf-8` first or `spec-ops health` fails with `UnicodeEncodeError` (PowerShell: `$env:PYTHONIOENCODING = "utf-8"`). If `uv run spec-ops` says the command is not found, run `uv tool update-shell` and open a new terminal.

## Troubleshooting

**Docker says it cannot connect, or `docker compose` hangs.** Docker Desktop is not running. Start it and wait until it says Docker is running.

**Port 8080 is already in use.** Edit the `ports` line in `docker-compose.yml`. See [Run with Docker](docs/how-to/run-with-docker.md#change-the-port).

**`uv` is not recognized or `command not found`.** Open a new terminal. If it still fails, add the uv folder to your PATH: `%USERPROFILE%\.local\bin` on Windows, `~/.local/bin` on macOS and Linux.

**PowerShell says `pnpm.ps1 cannot be loaded because running scripts is disabled`.** Allow local scripts for your user, then open a new terminal:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

You never need to activate a virtual environment. Always start Python tools with `uv run`.

**PDF download fails with `Chromium is not installed`.** Run `uv run career-buddy install-browser`. On Linux, if Chromium starts but reports missing libraries, run `uv run playwright install-deps chromium` (it asks for sudo). In Docker, Chromium is already included.

**The page at port 8000 shows JSON or a 404, not the app.** The UI is not built. Run `pnpm -C frontend build` (setup step 6).

**Port 8000 already in use (developer setup).** Pick another port. On macOS and Linux:

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
