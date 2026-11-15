"""Document use cases: tailor, clean and render a template, preview it, check it, and suggest rewordings."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field, replace

from career_graph.application.ports import DocumentRenderer, FactView, LLMUnavailable, MissingInputs, Rewriter, TextReader
from career_graph.domain.ats import Issue, check
from career_graph.domain.document import Document, Origin, Style
from career_graph.domain.markers import Change, clean, clean_document
from career_graph.domain.profile import Profile, assemble_profile
from career_graph.domain.rewording import verify_rewording
from career_graph.domain.tailoring import Report, apply_overrides, override_paragraphs, tailor
from career_graph.domain.templates import build_document, get_template


@dataclass(frozen=True)
class Rendered:
    data: bytes
    media_type: str
    filename: str
    issues: tuple[Issue, ...] = ()  # failed ATS checks: a warning, the file is still returned


@dataclass(frozen=True)
class TailorOptions:
    """What the user chose for one document: the job, which bullets to keep, and their own wording."""

    job_text: str = ""
    selection: frozenset[str] | None = None  # bullet fact ids; None means the template's top-k
    overrides: dict[str, str] = field(default_factory=dict)  # bullet fact id -> user text
    inputs: dict[str, str] = field(default_factory=dict)  # template inputs: company, role, ...


@dataclass(frozen=True)
class Preview:
    document: Document
    report: Report
    markers: list[Change]
    format: str = "docx"
    issues: tuple[Issue, ...] = ()  # ATS check of the document rendered in `format`


@dataclass(frozen=True)
class Suggestion:
    fact_id: str
    before: str
    after: str


@dataclass(frozen=True)
class Rejection:
    fact_id: str
    reasons: list[str]


@dataclass(frozen=True)
class Suggestions:
    suggestions: list[Suggestion]
    rejected: list[Rejection]


class DocumentService:
    def __init__(
        self,
        graph: FactView,
        renderers: dict[str, DocumentRenderer],
        readers: dict[str, TextReader],
        rewriter: Rewriter | None = None,
    ) -> None:
        self._graph = graph
        self._renderers = renderers
        self._readers = readers
        self._rewriter = rewriter

    async def _build(self, template_id: str, options: TailorOptions) -> tuple[Document, Preview, Profile]:
        spec = get_template(template_id)  # KeyError: unknown template
        if missing := [name for name in spec.required if not options.inputs.get(name, "").strip()]:
            raise MissingInputs(", ".join(missing))
        profile = assemble_profile(await self._graph.snapshot())
        tailored, report = tailor(profile, options.job_text, spec, options.selection)
        tailored = override_paragraphs(tailored, options.overrides)
        doc, markers = clean_document(apply_overrides(build_document(tailored, spec, options.inputs), options.overrides))
        return doc, Preview(doc, report, markers), profile

    @property
    def formats(self) -> list[str]:
        return list(self._renderers)

    async def _file(self, doc: Document, fmt: str, style: Style) -> tuple[DocumentRenderer, bytes, tuple[Issue, ...]]:
        """Render, then read the bytes back with a TextReader and compare with what we meant to print."""
        renderer = self._renderers[fmt]  # KeyError: unknown format
        data = await asyncio.to_thread(renderer.render, doc, style)  # PDF drives a browser: keep it off the loop
        issues = await asyncio.to_thread(lambda: tuple(check(doc, self._readers[fmt].read(data))))
        return renderer, data, issues

    async def preview(
        self, template_id: str, options: TailorOptions = TailorOptions(), fmt: str = "docx", style: Style = Style()
    ) -> Preview:
        doc, preview, _ = await self._build(template_id, options)
        return replace(preview, format=fmt, issues=(await self._file(doc, fmt, style))[2])

    async def render(
        self, template_id: str, fmt: str, style: Style = Style(), options: TailorOptions = TailorOptions()
    ) -> Rendered:
        doc, _, profile = await self._build(template_id, options)
        renderer, data, issues = await self._file(doc, fmt, style)
        stem = re.sub(r"[^A-Za-z0-9]+", "-", profile.name).strip("-") or "Candidate"
        kind = re.sub(r"[^A-Za-z0-9]+", "-", doc.label).strip("-")
        return Rendered(data, renderer.media_type, f"{stem}-{kind}.{renderer.extension}", issues)

    async def check(
        self, template_id: str, fmt: str, style: Style = Style(), options: TailorOptions = TailorOptions()
    ) -> list[Issue]:
        return list((await self.render(template_id, fmt, style, options)).issues)

    async def suggest(self, template_id: str, options: TailorOptions) -> Suggestions:
        """LLM rewordings of the bullets the document would show. Only those that pass the verifier come back."""
        if self._rewriter is None:
            raise LLMUnavailable("No LLM is configured")
        spec = get_template(template_id)
        profile = assemble_profile(await self._graph.snapshot())
        tailored, report = tailor(profile, options.job_text, spec, options.selection)
        skills = [*profile.skills, *(s for p in profile.positions for s in p.skills)]
        protected = [*(t for p in profile.positions for t in (p.title, p.organization)),
                     *(t for e in profile.education for t in (e.degree, e.school))]
        rows = [(aid, text) for p in tailored.positions for text, aid in zip(p.achievements, p.achievement_ids)
                if aid not in options.overrides]

        async def reword(source: str) -> tuple[str, list[str]]:
            text, _ = clean(await self._rewriter.rewrite(source, report.matched), Origin.SUGGESTION)
            return text, verify_rewording(source, text, skills, protected, report.missing)

        results = await asyncio.gather(*(reword(text) for _, text in rows))
        out = Suggestions([], [])
        for (aid, source), (text, reasons) in zip(rows, results):
            if reasons:
                out.rejected.append(Rejection(aid, reasons))
            elif text != source:
                out.suggestions.append(Suggestion(aid, source, text))
        return out
