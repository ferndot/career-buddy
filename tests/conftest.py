"""Shared fixtures. PDF tests skip cleanly when Chromium is not installed."""

import os

import pytest

from career_graph.adapters.outputs.render_pdf import INSTALL_HINT

# moto's in-process S3 only answers AWS hostnames unless told about others, and it reads this once, on import.
os.environ.setdefault("MOTO_S3_CUSTOM_ENDPOINTS", "http://minio.test:9000")
# Tests never touch the real OS keychain: API keys go to a file in each test's own data folder.
os.environ["CAREER_GRAPH_KEY_STORE"] = "file"


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
