"""Renders a Document to PDF by printing the single-column HTML page with Chromium (Playwright)."""

from __future__ import annotations

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from career_buddy.adapters.outputs.render_html import html_page
from career_buddy.application.ports import RendererUnavailable
from career_buddy.domain.document import Document, Style

_PAPER = {"letter": "Letter", "a4": "A4"}
_PRINT_CSS = "body{max-width:none;margin:0;padding:0}"
INSTALL_HINT = "Chromium is not installed: run `career-buddy install-browser` once (it runs `playwright install chromium`)"


class PdfRenderer:
    format = "pdf"
    extension = "pdf"
    media_type = "application/pdf"

    def __init__(self, executable_path: str | None = None) -> None:
        self._executable_path = executable_path

    def render(self, doc: Document, style: Style) -> bytes:
        html = html_page(doc, style, _PRINT_CSS)
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(executable_path=self._executable_path)
            except PlaywrightError as error:
                if "doesn't exist" in str(error) or "Executable" in str(error):
                    raise RendererUnavailable(INSTALL_HINT) from error
                raise
            try:
                page = browser.new_page()
                page.set_content(html)
                return page.pdf(
                    format=_PAPER[style.paper],
                    margin={side: "0.75in" for side in ("top", "right", "bottom", "left")},
                    tagged=True,
                    print_background=True,  # off by default: the header band and side panel would print white, the band's white text on white
                )
            finally:
                browser.close()
