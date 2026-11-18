"""Request bodies for the tailoring and document routes."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from career_buddy.application.documents import TailorOptions
from career_buddy.domain.document import Style
from career_buddy.domain.generation import ResumeLength
from career_buddy.domain.written import Section, WrittenDocument


class TailorRequest(BaseModel):
    template: str
    job_text: str = ""
    overrides: dict[str, str] = {}  # bullet fact id -> the user's own wording
    inputs: dict[str, str] = {}  # template inputs: company, role, interviewer, ...

    @property
    def options(self) -> TailorOptions:
        return TailorOptions(self.job_text, self.overrides, self.inputs)


class SuggestRequest(TailorRequest):
    job_text: str = Field(min_length=1)


class GenerateRequest(TailorRequest):
    instructions: str = Field("", max_length=2000)  # the user's free-text directions for the writer; empty is fine
    pinned: list[str] = Field([], max_length=500)  # slot ids the user wrote themselves: the writer leaves them alone
    resume_pages: ResumeLength = "default"  # how long a resume should be; a letter ignores it
    template_instructions: str = Field("", max_length=4000)  # how the chosen template and letter style want the text written; empty adds none
    font: Literal["sans", "serif"] = "sans"  # the style the length is measured in
    paper: Literal["letter", "a4"] = "letter"


class PreviewRequest(TailorRequest):
    format: str = "docx"  # the format whose ATS check the preview reports


class DocumentRequest(PreviewRequest):
    format: str
    font: Literal["sans", "serif"] = "sans"
    paper: Literal["letter", "a4"] = "letter"

    @property
    def style(self) -> Style:
        return Style(self.font, self.paper)


class SaveRequest(TailorRequest):
    """No format: a saved document is kept as html and converted when it is downloaded."""

    font: Literal["sans", "serif"] = "sans"
    paper: Literal["letter", "a4"] = "letter"
    label: str = ""  # a name for the saved document; empty means the file name
    sections: list[Section] = Field([], max_length=12)  # what the writer wrote (a draft's `sections`): the structure of the document, kept apart from `overrides`, which is the user's own wording
    instructions: str = Field("", max_length=2000)  # the user's directions for the writer, kept for regenerating
    resume_pages: ResumeLength = "default"  # this resume's length, kept for regenerating
    template_instructions: str = Field("", max_length=4000)  # the template's instructions, kept for regenerating

    @property
    def written(self) -> WrittenDocument | None:
        return WrittenDocument(sections=tuple(self.sections)) if self.sections else None

    @property
    def style(self) -> Style:
        return Style(self.font, self.paper)
