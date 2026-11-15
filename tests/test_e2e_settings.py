"""Browser journey: add an LLM connection in Settings, make it active, and see the choice survive a reload."""

import httpx
from playwright.sync_api import Page, expect

FAKE_KEY = "sk-fake-1234567890abcdef-a1f2"


def open_connections(page: Page) -> None:
    page.click('[data-step="settings"]')
    expect(page.locator("#step-settings")).to_be_visible()
    expect(page.get_by_role("tab", name="LLM connections")).to_have_attribute("aria-selected", "true")


def test_adding_and_activating_a_connection(page: Page, live_server: str) -> None:
    open_connections(page)
    expect(page.locator("#llm-empty")).to_be_visible()
    expect(page.locator(".primary:visible")).to_have_count(1)

    page.click("#llm-add")
    expect(page.locator(".primary:visible")).to_have_count(1)  # now the Save button
    page.select_option("#llm-preset", "ollama")
    expect(page.locator("#llm-url")).to_have_value("http://localhost:11434/v1")
    page.select_option("#llm-preset", "llamacpp")
    expect(page.locator("#llm-url")).to_have_value("http://localhost:9931/v1")
    page.select_option("#llm-preset", "anthropic")
    expect(page.locator("#llm-url")).to_have_value("https://api.anthropic.com/v1")
    expect(page.locator("#llm-url")).to_have_attribute("readonly", "")  # a cloud address cannot be edited
    page.select_option("#llm-preset", "custom")
    page.fill("#llm-url", "http://192.168.1.20:8080/v1")
    expect(page.locator("#llm-private")).to_be_visible()  # a private address gets a warning
    page.fill("#llm-url", "http://localhost:8080/v1")
    expect(page.locator("#llm-private")).to_be_hidden()
    page.fill("#llm-label", "My local server")
    page.fill("#llm-model", "qwen3")
    page.fill("#llm-key", FAKE_KEY)
    page.click("#llm-save")

    card = page.locator("#llm-list li")
    expect(card).to_have_count(1)
    expect(card).to_contain_text("My local server")
    expect(card).to_contain_text("http://localhost:8080/v1")
    expect(card).to_contain_text("sk-...a1f2")
    expect(card).to_contain_text("Stays on this computer")
    expect(card).not_to_contain_text(FAKE_KEY)
    expect(card.locator(".badge")).to_have_count(0)  # saved, but not active yet
    for name in ("Test", "Set active", "Edit", "Delete"):
        expect(card.get_by_role("button", name=name)).to_be_visible()
        assert card.get_by_role("button", name=name).bounding_box()["height"] >= 44
    assert FAKE_KEY not in page.content()

    card.get_by_role("button", name="Set active").click()
    expect(card.locator(".badge")).to_have_text("Active")
    expect(card.get_by_role("button", name="Turn off")).to_be_visible()
    assert httpx.get(f"{live_server}/api/llm/connections").json()["active"] == card.get_attribute("data-id")

    page.reload()
    open_connections(page)
    expect(page.locator("#llm-list .badge")).to_have_text("Active")

    page.locator("#llm-list li").get_by_role("button", name="Turn off").click()
    expect(page.locator("#llm-list .badge")).to_have_count(0)
    assert page.errors == []


def test_the_settings_page_fits_a_phone(page: Page) -> None:
    page.set_viewport_size({"width": 375, "height": 812})
    open_connections(page)
    page.click("#llm-add")
    page.wait_for_timeout(200)
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    for field in page.locator("#llm-form input:visible, #llm-form select, #llm-form button:visible").all():
        assert field.bounding_box()["height"] >= 44
