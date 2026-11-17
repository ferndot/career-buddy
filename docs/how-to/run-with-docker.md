# Run with Docker

Use this to run career-buddy without installing Python or Node.

You need [Docker](https://docs.docker.com/get-docker/) running.

## Start

From the project folder, on any OS:

```bash
docker compose up --build -d
```

Open http://localhost:8080. One container serves the web app and the API. API documentation is at http://localhost:8080/docs.

On macOS and Linux, `make` does the same. On Windows, `make` is usually not installed, so use the command above.

## Stop and read the log

```bash
docker compose down
```

```bash
docker compose logs -f career-buddy
```

`make stop` and `make logs` do the same.

## Where your data is

Your data is in `./data` on the host, mounted as `/data` in the container. It survives rebuilds and restarts. API keys are kept in `secrets.json` in that folder, because the image sets `CAREER_BUDDY_KEY_STORE=file`.

## Change the port

The app listens on port 8000 inside the container and is published as `127.0.0.1:8080`. To change the host port, edit the `ports` line in `docker-compose.yml`.

## Reach a model on your computer

Inside the container, `localhost` is the container. Use these addresses in **Settings** instead:

- Ollama: `http://host.docker.internal:11434/v1`
- LM Studio: `http://host.docker.internal:1234/v1`

## Chromium

Chromium for PDF output is already in the image. You do not run `install-browser`.
