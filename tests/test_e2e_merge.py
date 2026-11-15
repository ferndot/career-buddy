"""Browser journeys for duplicates: confirm a merge and see one employer, and say two facts are not the same."""

import re

from playwright.sync_api import Page, expect

from test_api import linkedin_zip
from test_editing_api import PDF_TEXT


def open_edit_with_two_acmes(page: Page, live_server: str) -> None:
    page.set_input_files("#import-file", {"name": "export.zip", "mimeType": "application/zip", "buffer": linkedin_zip()})
    expect(page.locator("#step-edit")).to_be_visible()
    page.request.post(f"{live_server}/api/import/file", multipart={"file": {"name": "resume.txt", "mimeType": "text/plain", "buffer": PDF_TEXT}})
    page.click('[data-step="create"]')
    page.click('[data-step="edit"]')
    expect(page.locator(".dup", has_text="Acme")).to_have_count(1)


def test_confirming_a_proposed_merge_leaves_one_employer_in_the_preview(page: Page, live_server: str) -> None:
    open_edit_with_two_acmes(page, live_server)
    page.locator(".dup", has_text="Acme").get_by_role("button", name="Merge").click()
    expect(page.locator(".dup")).to_have_count(0)

    page.click('[data-step="create"]')
    expect(page.locator("#preview h3", has_text="Globex")).to_have_count(1)
    headings = page.locator("#preview h3", has_text="Acme").all_text_contents()
    assert len(headings) == 2  # Senior Engineer and Platform Lead, at one employer
    assert len({re.search(r", (Acme[^(]*?) \(", h)[1] for h in headings}) == 1
    assert page.errors == []


def test_not_the_same_is_remembered_by_the_server(page: Page, live_server: str) -> None:
    open_edit_with_two_acmes(page, live_server)
    page.locator(".dup", has_text="Acme").get_by_role("button", name="Not the same").click()
    expect(page.locator(".dup")).to_have_count(0)
    assert page.request.get(f"{live_server}/api/duplicates").json() == []
    page.reload()
    page.click('[data-step="edit"]')
    expect(page.locator(".dup")).to_have_count(0)
    assert page.errors == []
