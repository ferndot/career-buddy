"""Shared fixtures. Browser-backed tests skip cleanly when Chromium is not installed."""

import os
import socket
import threading
import time
from pathlib import Path

import pytest

from career_graph.adapters.outputs.render_pdf import INSTALL_HINT

# moto's in-process S3 only answers AWS hostnames unless told about others, and it reads this once, on import.
os.environ.setdefault("MOTO_S3_CUSTOM_ENDPOINTS", "http://minio.test:9000")


@pytest.fixture(scope="session")
def chromium() -> None:
    from playwright.sync_api import Error, sync_playwright

    try:
        with sync_playwright() as p:
            p.chromium.launch().close()
    except Error as error:
        if "doesn't exist" in str(error) or "Executable" in str(error):
            pytest.skip(INSTALL_HINT)
        raise


@pytest.fixture
def renderers(request: pytest.FixtureRequest) -> list:
    """Extra renderers for the live server. Parametrize indirectly to swap one in."""
    return getattr(request, "param", [])


@pytest.fixture
def llm(request: pytest.FixtureRequest):
    """An httpx MockTransport handler that plays the LLM for the live server. Parametrize indirectly; none by default."""
    return getattr(request, "param", None)


@pytest.fixture
def live_server(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, renderers: list, llm):
    """The real app on a free local port, with its own empty data directory."""
    import httpx
    import uvicorn

    from career_graph.web.app import create_app

    monkeypatch.delenv("CAREER_GRAPH_LLM_BASE_URL", raising=False)
    client = httpx.AsyncClient(transport=httpx.MockTransport(llm), base_url="http://llm.test/v1") if llm else None
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(create_app(tmp_path, llm_client=client, renderers=renderers), host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(10)


@pytest.fixture
def page(chromium, live_server: str):
    """A Chromium page on the app. `page.errors` collects uncaught script errors."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_context(accept_downloads=True, viewport={"width": 1280, "height": 900}).new_page()
        page.errors = []
        page.on("pageerror", lambda error: page.errors.append(str(error)))
        page.goto(live_server)
        yield page
        browser.close()
