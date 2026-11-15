"""Browser journeys: LLM suggestions in the Create step, and a position added from the editor."""

import json

import httpx
import pytest
from playwright.sync_api import Page, expect

from test_e2e_editor import RESUME, paste_resume

THREE = RESUME.replace(b"- Translated the Menabrea notes\n", b"- Translated the Menabrea notes\n- Corresponded with Babbage weekly\n")
JOB = "Requirements:\n- Python"
ANSWERS = {
    "Wrote the first published algorithm": "Authored the first published algorithm",
    "Translated the Menabrea notes": "Rendered the Menabrea notes",
    "Corresponded with Babbage weekly": "Corresponded with Babbage weekly in 1843",  # a new number: the verifier rejects it
}


EXTRACTED = {"name": "Ada Lovelace", "positions": [{"title": "Analyst", "organization": "Analytical Society", "period": "2010 - 2015",
                                                    "achievements": list(ANSWERS)}]}


def mock_llm(request: httpx.Request) -> httpx.Response:
    messages = json.loads(request.content)["messages"]
    if messages[0]["content"].startswith("Extract a career history"):  # an active connection also reads imports
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(EXTRACTED)}}]})
    source = messages[-1]["content"]
    return httpx.Response(200, json={"choices": [{"message": {"content": ANSWERS.get(source, source)}}]})


def open_create(page: Page, resume: bytes = RESUME) -> None:
    page.set_input_files("#import-file", {"name": "resume.txt", "mimeType": "text/plain", "buffer": resume})
    expect(page.locator("#step-edit")).to_be_visible()
    page.click('[data-step="create"]')
    expect(page.locator("#preview")).to_contain_text("Ada Lovelace")


def test_the_ui_says_so_when_no_llm_is_configured(page: Page) -> None:
    open_create(page)
    page.click("#suggest")
    expect(page.locator("#suggestions")).to_contain_text("Paste a job posting")
    page.fill("#job-text", JOB)
    page.click("#suggest")
    expect(page.locator("#suggestions")).to_contain_text("No LLM is configured")
    expect(page.locator("#suggestions button")).to_have_count(0)
    assert page.errors == []


@pytest.mark.parametrize("llm", [mock_llm], indirect=True)
def test_suggestions_show_with_accept_and_reject_and_only_verified_ones_appear(page: Page) -> None:
    open_create(page, THREE)
    page.fill("#job-text", JOB)
    page.click("#suggest")
    items = page.locator("#suggestions li")
    expect(items).to_have_count(2)  # the one with a new number was rejected by the verifier
    expect(items.first).to_contain_text("Wrote the first published algorithm")
    expect(items.first).to_contain_text("Authored the first published algorithm")
    expect(page.locator("#suggestions")).not_to_contain_text("1843")

    items.first.get_by_role("button", name="Accept").click()
    expect(page.locator("#preview")).to_contain_text("Authored the first published algorithm")
    expect(page.locator("#preview")).not_to_contain_text("Wrote the first published algorithm")
    expect(items).to_have_count(1)

    items.first.get_by_role("button", name="Reject").click()
    expect(items).to_have_count(0)
    expect(page.locator("#preview")).to_contain_text("Translated the Menabrea notes")
    assert page.errors == []


def test_adding_a_position_and_an_education_from_the_editor_shows_in_the_preview(page: Page) -> None:
    paste_resume(page)
    page.click("#add-position summary")
    page.fill("#pos-title", "Consultant")
    page.fill("#pos-org", "Initech")
    page.fill("#pos-dates", "2016 - 2018")
    page.fill("#pos-bullets", "Saved the day\nShipped the engine")
    page.click("#pos-save")
    expect(page.locator("#edit-status")).to_have_text("All changes saved")
    expect(page.frame_locator("iframe.gjs-frame").locator('[data-field="title"]', has_text="Consultant")).to_be_visible()

    page.click("#add-education summary")
    page.fill("#edu-degree", "BSc Mathematics")
    page.fill("#edu-school", "University of London")
    page.click("#edu-save")
    expect(page.frame_locator("iframe.gjs-frame").locator('[data-field="degree"]', has_text="BSc Mathematics")).to_be_visible()

    page.click('[data-step="create"]')
    preview = page.locator("#preview")
    expect(preview).to_contain_text("Consultant, Initech (2016 - 2018)")
    expect(preview.locator("li", has_text="Saved the day")).to_have_count(1)
    expect(preview.locator("li", has_text="Shipped the engine")).to_have_count(1)
    expect(preview).to_contain_text("BSc Mathematics, University of London")
    assert page.errors == []
