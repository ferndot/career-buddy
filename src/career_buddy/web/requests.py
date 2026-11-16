"""Request bodies for the tailoring and document routes."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from career_buddy.application.documents import TailorOptions
from career_buddy.domain.document import Style


class TailorRequest(BaseModel):
    template: str
    job_text: str = ""
    selection: list[str] | None = None  # bullet fact ids to keep, in place of the template's top-k
    overrides: dict[str, str] = {}  # bullet fact id -> the user's own wording
    inputs: dict[str, str] = {}  # template inputs: company, role, interviewer, ...
    skill_ids: list[str] | None = None  # skill fact ids to keep, in place of the template's top-k
    education_ids: list[str] | None = None  # education fact ids to keep, in place of all

    @property
    def options(self) -> TailorOptions:
        def ids(chosen: list[str] | None) -> frozenset[str] | None:
            return None if chosen is None else frozenset(chosen)

        return TailorOptions(self.job_text, ids(self.selection), self.overrides, self.inputs, ids(self.skill_ids), ids(self.education_ids))


class SuggestRequest(TailorRequest):
    job_text: str = Field(min_length=1)


class PreviewRequest(TailorRequest):
    format: str = "docx"  # the format whose ATS check the preview reports


class DocumentRequest(PreviewRequest):
    format: str
    font: Literal["sans", "serif"] = "sans"
    paper: Literal["letter", "a4"] = "letter"

    @property
    def style(self) -> Style:
        return Style(self.font, self.paper)


class SaveRequest(DocumentRequest):
    label: str = ""  # a name for the saved document; empty means the file name
