"""Document use cases: tailor, clean and render a template, preview it, check it, and suggest rewordings."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Callable
from dataclasses import dataclass, field, replace

from career_buddy.application.ports import (
    DocumentRenderer, FactView, LLMUnavailable, MergedView, MissingInputs, Rewriter, TextReader,
)
from career_buddy.domain.ats import Issue, check
from career_buddy.domain.document import Document, Origin, Style
from career_buddy.domain.knowledge import knowledge
from career_buddy.domain.markers import Change, clean, clean_document
from career_buddy.domain.model import Fact
from career_buddy.domain.profile import Profile, assemble_profile
from career_buddy.domain.rewording import verify_rewording
from career_buddy.domain.slots import fact_texts
from career_buddy.domain.tailoring import Report, apply_overrides, override_paragraphs, tailor
from career_buddy.domain.templates import TemplateSpec, build_document, get_template, position_heading
from career_buddy.domain.written import WrittenDocument, to_document


@dataclass(frozen=True)
class Rendered:
    data: bytes
    media_type: str
    filename: str
    issues: tuple[Issue, ...] = ()  # failed ATS checks: a warning, the file is still returned


@dataclass(frozen=True)
class TailorOptions:
    """What the user chose for one document: the job and their own wording."""

    job_text: str = ""
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


@dataclass(frozen=True)
class Tailored:
    """What a template would show for a job: the reduced profile, the match report, and every fact with its merged aliases."""

    spec: TemplateSpec
    profile: Profile
    report: Report
    facts: dict[str, Fact]
    absorbed: dict[str, list[Fact]]


class _NoMerges:
    async def absorbed(self) -> dict:
        return {}


class DocumentService:
    def __init__(
        self,
        graph: FactView,
        renderers: dict[str, DocumentRenderer],
        readers: dict[str, TextReader],
        rewriter: Callable[[], Rewriter | None] = lambda: None,  # asked at each request: a model can be connected after start
        merged: MergedView | None = None,
    ) -> None:
        self._graph = graph
        self._renderers = renderers
        self._readers = readers
        self._rewriter = rewriter
        self._merged = merged or _NoMerges()

    async def _build(self, template_id: str, options: TailorOptions) -> tuple[Document, Preview, Profile]:
        spec = get_template(template_id)  # KeyError: unknown template
        if missing := [name for name in spec.required if not options.inputs.get(name, "").strip()]:
            raise MissingInputs(", ".join(missing))
        profile = assemble_profile(await self._graph.snapshot())
        tailored, report = tailor(profile, options.job_text)
        tailored = override_paragraphs(tailored, options.overrides)
        doc, markers = clean_document(apply_overrides(build_document(tailored, spec, options.inputs), options.overrides))
        return doc, Preview(doc, report, markers), profile

    async def tailored(self, template_id: str, options: TailorOptions) -> Tailored:
        spec = get_template(template_id)  # KeyError: unknown template
        if missing := [name for name in spec.required if not options.inputs.get(name, "").strip()]:
            raise MissingInputs(", ".join(missing))
        batch = await self._graph.snapshot()
        profile, report = tailor(assemble_profile(batch), options.job_text)
        return Tailored(spec, profile, report, {f.id: f for f in batch.facts}, await self._merged.absorbed())

    async def lookup(self) -> dict[tuple[str, str], str]:
        """What the facts say now, for resolving a saved document's slots."""
        return fact_texts(assemble_profile(await self._graph.snapshot()))

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

    async def compose(self, template_id: str, options: TailorOptions = TailorOptions(), written: WrittenDocument | None = None) -> tuple[Document, str]:
        """The document for these options and the stem of its file name, with no file rendered. With `written`, its sections are the
        document's: the header and layout are the template's, the structure and text are the writer's."""
        doc, _, profile = await self._build(template_id, replace(options, overrides={}) if written else options)
        if written:
            doc = to_document(doc, get_template(template_id), written, {p.id: position_heading(p) for p in profile.positions if p.id})
        stem = re.sub(r"[^A-Za-z0-9]+", "-", profile.name).strip("-") or "Candidate"
        return doc, f"{stem}-{re.sub(r'[^A-Za-z0-9]+', '-', doc.label).strip('-')}"

    async def export(self, doc: Document, fmt: str, style: Style, stem: str) -> Rendered:
        """A document in one format, with its ATS check. KeyError: unknown format."""
        renderer, data, issues = await self._file(doc, fmt, style)
        return Rendered(data, renderer.media_type, f"{stem}.{renderer.extension}", issues)

    async def render(
        self, template_id: str, fmt: str, style: Style = Style(), options: TailorOptions = TailorOptions()
    ) -> Rendered:
        doc, stem = await self.compose(template_id, options)
        return await self.export(doc, fmt, style, stem)

    async def check(
        self, template_id: str, fmt: str, style: Style = Style(), options: TailorOptions = TailorOptions()
    ) -> list[Issue]:
        return list((await self.render(template_id, fmt, style, options)).issues)

    async def suggest(self, template_id: str, options: TailorOptions) -> Suggestions:
        """LLM wording for the bullets the document would show, written from each achievement's knowledge.
        Only those that pass the verifier come back."""
        rewriter = self._rewriter()
        if rewriter is None:
            raise LLMUnavailable("No LLM is configured")
        spec = get_template(template_id)
        batch = await self._graph.snapshot()
        profile = assemble_profile(batch)
        tailored, report = tailor(profile, options.job_text)
        skills = [*profile.skills, *(s for p in profile.positions for s in p.skills)]
        protected = [*(t for p in profile.positions for t in (p.title, p.organization)),
                     *(t for e in profile.education for t in (e.degree, e.school))]
        facts = {f.id: f for f in batch.facts}
        absorbed = await self._merged.absorbed()
        rows = [(aid, text) for p in tailored.positions for text, aid in zip(p.achievements, p.achievement_ids)
                if aid not in options.overrides]

        def source_of(aid: str, shown: str) -> str:
            return knowledge(facts[aid], absorbed.get(aid, ())) if aid in facts else shown

        async def reword(aid: str, shown: str) -> tuple[str, list[str]]:
            source = source_of(aid, shown)
            text, _ = clean(await rewriter.rewrite(source, report.matched, options.job_text), Origin.SUGGESTION)
            return text, verify_rewording(source, text, skills, protected, report.missing)

        results = await asyncio.gather(*(reword(aid, text) for aid, text in rows))
        out = Suggestions([], [])
        for (aid, shown), (text, reasons) in zip(rows, results):
            if reasons:
                out.rejected.append(Rejection(aid, reasons))
            elif text != shown:
                out.suggestions.append(Suggestion(aid, shown, text))
        return out
