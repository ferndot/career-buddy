"""Ports: what the application needs from the outside world. Adapters implement these."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Protocol

from career_graph.domain.ats import Extracted
from career_graph.domain.document import Document, Style
from career_graph.domain.events import Event
from career_graph.domain.model import FactBatch


class FactExtractor(Protocol):
    """Inference: free text in, facts out. Heuristic or model-backed."""

    async def extract(self, text: str, source: str) -> FactBatch: ...


class SourceParser(Protocol):
    """A structured export (e.g. LinkedIn) in, facts out. Files are name -> bytes."""

    def parse(self, files: dict[str, bytes], source: str) -> FactBatch: ...


class EventLog(Protocol):
    def append(self, event: Event) -> None: ...

    def replay(self) -> Iterable[Event]: ...


class FactView(Protocol):
    """What readers see: the facts after revisions and merges."""

    async def snapshot(self) -> FactBatch: ...


class FactGraph(FactView, Protocol):
    """Read/write store of imported facts. Rebuilt from the event log on startup."""

    async def apply(self, batch: FactBatch) -> None: ...


class FactNotFound(Exception):
    """No visible fact has this id."""


class UnreadableDocument(Exception):
    """The bytes are not a readable document of the expected type."""


class NoTextLayer(UnreadableDocument):
    """A PDF with no extractable text (a scan). OCR is out of scope."""


class UnsupportedFileType(Exception):
    """No reader handles this file extension."""


class TextReader(Protocol):
    """Reads a file back to text and structure. Serves import and the ATS check."""

    def read(self, data: bytes) -> Extracted: ...


class DocumentRenderer(Protocol):
    format: str
    extension: str
    media_type: str

    def render(self, doc: Document, style: Style) -> bytes: ...


class RendererUnavailable(Exception):
    """A renderer cannot run here, for example Chromium is not installed for PDF."""


class MissingInputs(Exception):
    """The template needs inputs the request did not give. Carries their names."""


class LLMUnavailable(Exception):
    """No LLM is configured, or the one configured did not answer."""


class Rewriter(Protocol):
    """Optional LLM polish for one bullet. Its output is never trusted: it goes through `verify_rewording`."""

    async def rewrite(self, text: str, terms: Sequence[str]) -> str: ...


class ObjectNotFound(Exception):
    """No object is stored under this key."""


class ObjectStore(Protocol):
    """Opaque blobs by key, such as original uploads. Keys look like `sources/<sha256>.pdf`."""

    def put(self, key: str, data: bytes, content_type: str) -> None: ...

    def get(self, key: str) -> bytes: ...

    def exists(self, key: str) -> bool: ...

    def delete(self, key: str) -> None:
        """Idempotent: deleting a missing key is not an error."""
