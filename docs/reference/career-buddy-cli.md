# career-buddy command

The `career-buddy` command is defined in `pyproject.toml` as `career_buddy:main`. Run it with `uv run career-buddy`.

| Command | What it does |
|---|---|
| `uv run career-buddy` | Starts the server at `http://127.0.0.1:8000` (or `HOST` and `PORT`) and opens it in your browser. |
| `uv run career-buddy install-browser` | Downloads Chromium for PDF output (about 150 MB, stored outside the project). It runs `playwright install chromium`. |

It takes no other arguments. Set behavior with environment variables: see [Configuration](configuration.md).

The separate `spec-ops` command is the SpecOps project tool. See the [SpecOps CLI reference](cli.md).
