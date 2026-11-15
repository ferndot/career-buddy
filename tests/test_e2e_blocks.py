"""The GrapesJS canvas is locked to ATS-safe blocks: no arbitrary HTML, no absolute layout. Tested in Chromium."""

from playwright.sync_api import Page, expect

from test_e2e_editor import canvas, paste_resume

ALLOWED = {"cg-section", "cg-heading", "cg-paragraph", "cg-list", "cg-item", "textnode"}
HOSTILE = (
    '<table><tr><td>cell</td></tr></table><div style="position:absolute;left:9px">floating</div>'
    '<img src="x.png"><script>window.pwned = 1</script><p onclick="window.pwned = 2" style="color:red">styled</p>'
)


def test_only_the_locked_block_types_exist_in_the_canvas(page: Page) -> None:
    paste_resume(page)
    types = page.evaluate("cg.editor.getWrapper().find('*').map(c => c.get('type'))")
    assert types and set(types) <= ALLOWED and {"cg-section", "cg-heading", "cg-list", "cg-item"} <= set(types)


def test_blocks_cannot_be_dragged_cloned_or_dropped_into(page: Page) -> None:
    paste_resume(page)
    flags = page.evaluate(
        """() => cg.editor.getWrapper().find('*').filter(c => c.get('type') !== 'textnode').map(c => ({
            type: c.get('type'), draggable: c.get('draggable'), copyable: c.get('copyable'),
            removable: c.get('removable'), droppable: c.get('droppable')}))"""
    )
    assert all(f["draggable"] is False and f["copyable"] is False and f["droppable"] is False for f in flags)
    assert {f["type"] for f in flags if f["removable"]} == set()  # hiding goes through the undo-able command
    assert page.evaluate("cg.editor.BlockManager.getAll().length") == 0  # nothing to drop onto the page


def test_foreign_html_added_to_the_canvas_is_stripped(page: Page) -> None:
    paste_resume(page)
    page.evaluate("(html) => { cg.editor.getWrapper().find('[data-cg=section]')[0].append(html); }", HOSTILE)
    page.wait_for_timeout(200)
    frame = canvas(page)
    for selector in ("table", "img", "script", "div[style]", "[style*=absolute]", "[onclick]"):
        expect(frame.locator(selector)).to_have_count(0)
    assert page.evaluate("window.pwned") is None
    assert set(page.evaluate("cg.editor.getWrapper().find('*').map(c => c.get('type'))")) <= ALLOWED


def test_pasting_html_into_a_field_inserts_plain_text_only(page: Page) -> None:
    paste_resume(page)
    bullet = canvas(page).locator('[data-cg="item"][data-field="bullet"]').first
    bullet.dblclick()
    page.keyboard.press("Control+A")
    bullet.evaluate(
        """el => { const data = new DataTransfer();
            data.setData('text/html', '<table><tr><td>cell</td></tr></table>'); data.setData('text/plain', 'plain words');
            el.dispatchEvent(new ClipboardEvent('paste', {clipboardData: data, bubbles: true, cancelable: true})); }"""
    )
    page.keyboard.press("Enter")  # fields are single-line: Enter adds nothing
    canvas(page).locator('[data-field="title"]').first.click()
    expect(canvas(page).locator("table")).to_have_count(0)
    expect(canvas(page).locator('[data-cg="item"]').first).to_have_text("plain words")
    assert page.evaluate("cg.editor.getWrapper().find('br').length") == 0
