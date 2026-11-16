"""Live provider checks. Skipped unless CAREER_BUDDY_LIVE_<PROVIDER>_KEY is set. They only list models: no resume text, no cost."""

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from career_buddy.web.app import create_app

pytestmark = pytest.mark.live


@pytest.mark.parametrize("provider", ["anthropic", "gemini"])
def test_the_real_provider_accepts_the_key_and_lists_models(provider: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    key = os.environ.get(f"CAREER_BUDDY_LIVE_{provider.upper()}_KEY")
    if not key:
        pytest.skip(f"set CAREER_BUDDY_LIVE_{provider.upper()}_KEY to run this against the real service")
    monkeypatch.delenv("CAREER_BUDDY_LLM_BASE_URL", raising=False)
    with TestClient(create_app(tmp_path)) as client:
        made = client.post("/api/llm/connections", json={"preset": provider, "model": "unused", "api_key": key})
        result = client.post("/api/llm/test", json={"id": made.json()["id"]}).json()
    assert result["ok"] is True and result["models"], result["message"]
    assert key not in str(result)
