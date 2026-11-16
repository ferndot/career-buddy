"""Serves the built React app that ships inside the package (built by `pnpm build` in frontend/)."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

UI_DIR = Path(__file__).resolve().parent / "static"


class SpaFiles(StaticFiles):
    """Unknown paths load index.html so the React router handles them. Unknown /api paths stay 404."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        if scope["method"] not in ("GET", "HEAD") or path.replace("\\", "/").lstrip("/").split("/")[0] == "api":
            raise StarletteHTTPException(status_code=404)
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as error:
            # Files that are not there (such as /events.jsonl) stay 404; only app routes get index.html.
            if error.status_code != 404 or "." in path.rsplit("/", 1)[-1]:
                raise
            return await super().get_response("index.html", scope)


def mount_ui(api: FastAPI) -> None:
    # Must run after every API route is added: a mount at "/" would otherwise shadow the routes registered after it.
    if UI_DIR.is_dir():
        api.mount("/", SpaFiles(directory=UI_DIR, html=True), name="ui")
