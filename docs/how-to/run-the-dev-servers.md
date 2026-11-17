# Run the development servers

Use this to edit the web UI with hot reload, or the backend with auto-reload. Finish the setup in the [README](../../README.md#setup) first.

## From source

Use two terminals, both in the project folder.

Terminal 1, the backend on http://127.0.0.1:8000:

```bash
uv run career-buddy
```

Terminal 2, the frontend on http://localhost:5173:

```bash
pnpm -C frontend dev
```

Open http://localhost:5173. The frontend forwards `/api` to the backend.

## Backend auto-reload

Set `RELOAD=1` to restart the backend when a source file changes. The browser does not open in this mode. On macOS and Linux:

```bash
RELOAD=1 uv run career-buddy
```

On Windows (PowerShell):

```powershell
$env:RELOAD = "1"; uv run career-buddy
```

## Backend on another port

Set `PORT` for the backend, and `API_TARGET` for the frontend so it knows where to forward. On macOS and Linux:

```bash
PORT=8001 uv run career-buddy
```

```bash
API_TARGET=http://127.0.0.1:8001 pnpm -C frontend dev
```

On Windows (PowerShell):

```powershell
$env:PORT = "8001"; uv run career-buddy
```

```powershell
$env:API_TARGET = "http://127.0.0.1:8001"; pnpm -C frontend dev
```

## With Docker

`make dev` runs the backend with auto-reload and the UI under hot reload inside containers. The UI is at http://localhost:5173. Press Ctrl+C to stop. Without `make`:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

## Rebuild the served UI

The backend at port 8000 serves the last built UI, not the dev server. After frontend changes, rebuild it:

```bash
pnpm -C frontend build
```
