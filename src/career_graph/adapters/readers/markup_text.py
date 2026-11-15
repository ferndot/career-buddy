"""Readers for Markdown, TXT and HTML output: remove the markup, keep the lines."""

from __future__ import annotations

import re
from html.parser import HTMLParser

from career_graph.domain.ats import Extracted

_MARKER = re.compile(r"^(?:#+\s+|[-*•]\s+)")


class PlainTextReader:
    """Markdown and plain text: drop heading hashes and bullet markers."""

    def read(self, data: bytes) -> Extracted:
        lines = [_MARKER.sub("", raw.strip()) for raw in data.decode("utf-8", "replace").splitlines() if raw.strip()]
        return Extracted(text="\n".join(lines), lines=lines)


class _Collector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.lines: list[str] = []
        self.tables = self.images = 0
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tables += tag == "table"
        self.images += tag in ("img", "svg")
        self._skip += tag in ("style", "script", "title")

    def handle_endtag(self, tag: str) -> None:
        self._skip -= tag in ("style", "script", "title")

    def handle_data(self, data: str) -> None:
        if not self._skip and data.strip():
            self.lines.append(data.strip())


class HtmlTextReader:
    def read(self, data: bytes) -> Extracted:
        parser = _Collector()
        parser.feed(data.decode("utf-8", "replace"))
        return Extracted(
            text="\n".join(parser.lines), lines=parser.lines, has_tables=parser.tables > 0, image_count=parser.images
        )
