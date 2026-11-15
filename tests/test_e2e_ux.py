"""Browser journeys for the plain-language UI: steps, empty states, feedback, ATS wording, mobile, focus, dark mode."""

import re

import pytest
from playwright.sync_api import Page, expect

from test_e2e_editor import RESUME, canvas, paste_resume
from test_ats_warning_api import DropsBullets

ORIGINAL = "Wrote the first published algorithm"


def edit_first_bullet(page: Page, text: str) -> None:
    bullet = canvas(page).locator('[data-cg="item"][data-field="bullet"]', has_text="first published algorithm")
    bullet.dblclick()
    page.keyboard.press("Control+A")
    page.keyboard.type(text)
    canvas(page).locator('[data-field="title"]').first.click()  # leaving the field saves it


def import_resume(page: Page) -> None:
    page.set_input_files("#import-file", {"name": "resume.txt", "mimeType": "text/plain", "buffer": RESUME})
    expect(page.locator("#step-edit")).to_be_visible()


def test_each_step_has_a_one_sentence_intro_and_exactly_one_primary_action(page: Page) -> None:
    expect(page.locator("#steps button")).to_have_text([re.compile("Sources"), re.compile("Career explorer"), re.compile("Generator"), re.compile("Settings")])
    for step in ("import", "edit", "create"):
        if step == "edit":
            paste_resume(page)
        elif step == "create":
            page.click("#to-create")
        else:
            expect(page.locator('#steps [data-step="import"]')).to_have_attribute("aria-current", "step")
        lead = page.locator(f"#step-{step} .lead")
        expect(lead).to_be_visible()
        text = lead.inner_text()
        assert 20 < len(text) < 160 and text.count(". ") == 0, text  # one short sentence
        expect(page.locator(".primary:visible")).to_have_count(1)
    expect(page.locator('#steps [data-step="create"]')).to_have_attribute("aria-current", "step")
    assert page.errors == []


@pytest.mark.parametrize("step", ["edit", "create"])
def test_a_step_with_no_facts_says_what_to_do_first(page: Page, step: str) -> None:
    page.click(f'[data-step="{step}"]')
    empty = page.locator(f"#{step}-empty")
    expect(empty).to_be_visible()
    expect(empty).to_contain_text("import")
    expect(page.locator("#gjs" if step == "edit" else "#preview")).not_to_be_visible()
    expect(page.locator(".primary:visible")).to_have_count(1)
    empty.get_by_role("button", name="Go to Import").click()
    expect(page.locator("#step-import")).to_be_visible()
    assert page.errors == []


def test_a_returning_user_is_offered_a_way_straight_back_to_their_profile(page: Page, live_server: str) -> None:
    expect(page.locator("#import-existing")).to_be_hidden()
    page.request.post(f"{live_server}/api/import/text", data={"text": RESUME.decode()})
    page.reload()
    expect(page.locator("#import-existing")).to_contain_text("Ada Lovelace")
    page.click("#existing-go")
    expect(page.locator("#step-edit")).to_be_visible()
    assert page.errors == []


def test_a_bad_file_gets_a_plain_error_announced_to_screen_readers(page: Page) -> None:
    page.set_input_files("#import-file", {"name": "notes.exe", "mimeType": "application/octet-stream", "buffer": b"MZ"})
    status = page.locator("#import-status")
    expect(status).to_have_attribute("role", "alert")
    expect(status).to_contain_text("couldn't import notes.exe")
    expect(status).to_contain_text("Unsupported file type")
    expect(page.locator("#step-import")).to_be_visible()
    assert page.errors == []


def test_pasting_nothing_asks_for_text_without_calling_the_server(page: Page) -> None:
    requests = []
    page.on("request", lambda r: requests.append(r.url) if "/api/import" in r.url else None)
    page.click("#paste summary")
    page.click("#paste-btn")
    expect(page.locator("#import-status")).to_have_attribute("role", "alert")
    expect(page.locator("#import-status")).to_contain_text("Paste your resume text first")
    assert requests == []


def test_import_shows_progress_and_a_second_click_does_nothing(page: Page) -> None:
    held = []
    page.route("**/api/import/text", lambda route: held.append(route))
    page.click("#paste summary")
    page.fill("#paste-text", RESUME.decode())
    page.click("#paste-btn")
    expect(page.locator("#import-status")).to_contain_text("Reading")
    expect(page.locator("#import-status")).to_have_attribute("data-state", "busy")
    expect(page.locator("#paste-btn")).to_be_disabled()
    held[0].continue_()
    expect(page.locator("#step-edit")).to_be_visible()
    assert len(held) == 1 and page.errors == []


def test_saving_shows_progress_then_confirms(page: Page) -> None:
    paste_resume(page)
    held = []
    page.route("**/api/facts/*", lambda route: held.append(route) if route.request.method == "PATCH" else route.continue_())
    edit_first_bullet(page, "Wrote the very first algorithm")
    expect(page.locator("#edit-status")).to_have_text("Saving...")
    held[0].continue_()
    expect(page.locator("#edit-status")).to_have_text("All changes saved")
    assert page.errors == []


def test_a_failed_save_says_so_in_plain_words_and_puts_the_old_text_back(page: Page) -> None:
    paste_resume(page)
    page.route("**/api/facts/*", lambda route: route.abort() if route.request.method == "PATCH" else route.continue_())
    edit_first_bullet(page, "Something else entirely")
    status = page.locator("#edit-status")
    expect(status).to_have_attribute("role", "alert")
    expect(status).to_contain_text("Couldn't save")
    expect(status).not_to_contain_text("Failed to fetch")
    expect(canvas(page).locator('[data-field="bullet"]', has_text=ORIGINAL)).to_be_visible()


@pytest.mark.parametrize("renderers", [[DropsBullets()]], indirect=True)
def test_the_ats_warning_is_written_as_sentences_not_codes(page: Page) -> None:
    import_resume(page)
    page.click('[data-step="create"]')
    expect(page.locator("#ats-badge")).to_have_text("Passes ATS check")
    expect(page.locator("#ats-detail")).to_be_hidden()
    with page.expect_download():
        page.click("#dl-txt")
    expect(page.locator("#ats-badge")).to_have_text("ATS warning")
    detail = page.locator("#ats-detail")
    expect(detail).to_be_visible()
    expect(detail).to_contain_text("did not come through")
    expect(detail).to_contain_text("headings")
    for code in ("coverage", "order", "headings,", "text_layer"):
        assert code not in detail.inner_text().split(), code
    expect(page.locator("#ats-format")).to_contain_text("software employers use")
    assert page.errors == []


def test_wording_flags_are_explained_not_labelled_weak_signal(page: Page) -> None:
    import_resume(page)
    page.click('[data-step="edit"]')
    canvas(page).locator('[data-cg="item"]', has_text="Menabrea").dblclick()
    page.keyboard.press("Control+A")
    page.keyboard.type("Translated the intricate Menabrea notes")
    canvas(page).locator('[data-field="title"]').first.click()
    expect(page.locator("#edit-status")).to_have_text("All changes saved")
    page.click("#to-create")
    expect(page.locator("#markers")).to_contain_text("Check the wording")
    expect(page.locator("#markers")).to_contain_text("intricate")
    expect(page.locator("#markers")).not_to_contain_text("weak signal")


def test_the_job_match_section_appears_only_once_there_is_a_posting(page: Page) -> None:
    import_resume(page)
    page.click('[data-step="create"]')
    expect(page.locator("#preview")).to_contain_text("Ada Lovelace")
    expect(page.locator("#match")).to_be_hidden()
    page.fill("#job-text", "Requirements:\n- Python\n- Terraform")
    expect(page.locator("#match")).to_be_visible()
    expect(page.locator("#missing")).to_contain_text("terraform")


@pytest.mark.parametrize("step", ["import", "edit", "create"])
def test_phone_width_has_no_sideways_scroll_and_big_tap_targets(page: Page, step: str) -> None:
    page.set_viewport_size({"width": 375, "height": 812})
    import_resume(page)
    page.click(f'[data-step="{step}"]')
    expect(page.locator(f"#step-{step}")).to_be_visible()
    page.wait_for_timeout(300)
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    for button in page.locator("#steps button, .primary:visible").all():
        assert button.bounding_box()["height"] >= 44
    for nav in page.locator("#steps button").all():
        assert nav.is_visible() and nav.bounding_box()["x"] + nav.bounding_box()["width"] <= 375
    assert page.errors == []


def test_every_stop_on_the_keyboard_path_shows_a_focus_ring(page: Page) -> None:
    seen = []
    for _ in range(5):
        page.keyboard.press("Tab")
        seen.append(page.evaluate(
            """() => { const el = document.activeElement;
                const target = el.id === 'import-file' ? document.getElementById('drop') : el;
                const style = getComputedStyle(target);
                return [el.id || el.tagName, style.outlineStyle !== 'none' && parseFloat(style.outlineWidth) >= 2]; }"""
        ))
    assert "import-file" in [name for name, _ in seen], seen
    assert all(ring for _, ring in seen), seen


def test_dark_mode_swaps_the_colours(page: Page) -> None:
    background = "getComputedStyle(document.body).backgroundColor"
    light = page.evaluate(background)
    page.emulate_media(color_scheme="dark")
    assert page.evaluate(background) != light
    page.emulate_media(color_scheme="light")
    assert page.evaluate(background) == light
