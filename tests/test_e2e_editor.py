"""Browser journeys through the three steps. Skipped when Chromium is not installed."""

import re

import pytest

from playwright.sync_api import Page, expect

from test_ats_warning_api import DropsBullets

RESUME = b"""Ada Lovelace
London, UK

Experience
Analyst at Analytical Society, 2010 - 2015
- Wrote the first published algorithm
- Translated the Menabrea notes
Skills
Mathematics, Python
"""
NEW_BULLET = "Wrote the first published algorithm for the Analytical Engine"


def canvas(page: Page):
    return page.frame_locator("iframe.gjs-frame")


def paste_resume(page: Page) -> None:
    page.click("#paste summary")
    page.fill("#paste-text", RESUME.decode())
    page.click("#paste-btn")
    expect(page.locator("#step-edit")).to_be_visible()


def test_import_then_edit_a_bullet_and_see_the_preview_change(page: Page) -> None:
    expect(page.locator("#step-import")).to_be_visible()
    paste_resume(page)

    bullet = canvas(page).locator('[data-cg="item"][data-field="bullet"]', has_text="first published algorithm")
    expect(bullet).to_be_visible()
    bullet.dblclick()
    page.keyboard.press("Control+A")
    page.keyboard.type(NEW_BULLET)
    with page.expect_response(lambda r: r.request.method == "PATCH" and "/api/facts/" in r.url) as patch:
        canvas(page).locator('[data-field="title"]').first.click()  # leaving the field autosaves it
    assert patch.value.ok

    page.click('[data-step="create"]')
    expect(page.locator("#preview")).to_contain_text(NEW_BULLET)
    expect(page.locator("#preview li", has_text=re.compile(r"^Wrote the first published algorithm$"))).to_have_count(0)
    assert page.errors == []


def test_hiding_a_bullet_offers_undo(page: Page) -> None:
    paste_resume(page)
    bullet = canvas(page).locator('[data-cg="item"][data-field="bullet"]', has_text="Menabrea")
    bullet.click()
    page.click(".gjs-toolbar-item[data-cg-command='hide']")
    expect(bullet).to_have_count(0)
    page.click("#toast button")
    expect(canvas(page).locator('[data-cg="item"]', has_text="Menabrea")).to_be_visible()
    assert page.errors == []


def test_template_to_a_downloaded_pdf_with_the_ats_badge(page: Page, tmp_path) -> None:
    page.set_input_files("#import-file", {"name": "resume.txt", "mimeType": "text/plain", "buffer": RESUME})
    expect(page.locator("#step-edit")).to_be_visible()

    page.click('[data-step="create"]')
    page.select_option("#kind", "letter")
    page.select_option("#template", "cover-letter")
    expect(page.locator("#create-status")).to_contain_text("Missing required input")
    expect(page.locator("#dl-pdf")).to_be_disabled()

    page.fill('#inputs [name="company"]', "Initech")
    page.fill('#inputs [name="role"]', "Analytical Engineer")
    page.fill("#job-text", "Requirements:\n- Python\n- Terraform")
    expect(page.locator("#preview")).to_contain_text("Analytical Engineer position at Initech")
    expect(page.locator("#missing")).to_contain_text("terraform")
    expect(page.locator("#matched")).to_contain_text("python")

    with page.expect_download() as download:
        page.click("#dl-pdf")
    file = download.value
    assert file.suggested_filename == "Ada-Lovelace-Cover-Letter.pdf"
    assert open(file.path(), "rb").read(5) == b"%PDF-"
    expect(page.locator("#ats-badge")).to_have_text("Passes ATS check")
    assert page.errors == []


def test_duplicate_banner_merges_and_undoes(page: Page, live_server: str) -> None:
    from test_api import linkedin_zip
    from test_editing_api import PDF_TEXT

    page.set_input_files("#import-file", {"name": "export.zip", "mimeType": "application/zip", "buffer": linkedin_zip()})
    expect(page.locator("#step-edit")).to_be_visible()
    page.request.post(f"{live_server}/api/import/file", multipart={"file": {"name": "resume.txt", "mimeType": "text/plain", "buffer": PDF_TEXT}})
    page.click('[data-step="create"]')
    page.click('[data-step="edit"]')

    banner = page.locator(".dup", has_text="Acme")
    expect(banner).to_have_count(1)
    banner.get_by_role("button", name="Merge").click()
    expect(page.locator(".dup")).to_have_count(0)
    page.click("#toast button")  # Undo
    expect(page.locator(".dup", has_text="Acme")).to_have_count(1)
    assert page.errors == []


@pytest.mark.parametrize("renderers", [[DropsBullets()]], indirect=True)
def test_a_failing_ats_check_warns_beside_the_download_button_but_still_downloads(page: Page) -> None:
    page.set_input_files("#import-file", {"name": "resume.txt", "mimeType": "text/plain", "buffer": RESUME})
    expect(page.locator("#step-edit")).to_be_visible()
    page.click('[data-step="create"]')
    expect(page.locator("#ats-badge")).to_have_text("Passes ATS check")  # the preview checks DOCX, which is sound
    with page.expect_download() as download:
        page.click("#dl-txt")
    assert download.value.suggested_filename == "Ada-Lovelace-Resume.txt"
    expect(page.locator("#ats-badge")).to_contain_text("ATS warning")
    expect(page.locator("#ats-detail")).to_contain_text("did not come through")
    assert page.errors == []
