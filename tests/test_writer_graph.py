"""The tool-calling writer with a fake chat model: it never makes more than two calls, whatever the model does, and a revision never
rewrites accepted text."""

import asyncio

from hypothesis import given, settings, strategies as st
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from career_buddy.adapters.inference.writer_graph import GraphDocumentWriter, report
from career_buddy.application.ports import LLMUnavailable
from career_buddy.domain.coverage import Checked, next_step
from career_buddy.domain.generation import Brief, BriefFact, Claim, Rejection
from career_buddy.domain.written import Bullet, Item, Section, WrittenDocument, merged, nodes

FACTS = (BriefFact("p1", "position", "Engineer at Acme"), BriefFact("a1", "achievement", "Built ETL jobs", "p1"), BriefFact("a2", "achievement", "Cut costs", "p1"))
BRIEF = Brief("resume", FACTS, sections=("experience",))


def doc(*texts: str) -> WrittenDocument:
    return WrittenDocument(sections=(Section(key="experience", items=(Item(position_id="p1", bullets=tuple(Bullet(text=t, fact_ids=(f"a{n}",)) for n, t in enumerate(texts, 1))),)),))


class Scripted(BaseChatModel):
    """Answers each call from `script`: a document (a tool call), None (text, no tool call) or an exception (the call fails)."""

    script: list = []
    calls: int = 0

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        step = self.script[self.calls]
        object.__setattr__(self, "calls", self.calls + 1)
        if isinstance(step, Exception):
            raise step
        calls = [{"name": "submit_document", "args": step.model_dump(), "id": f"c{self.calls}", "type": "tool_call"}] if step else []
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content="" if calls else "text", tool_calls=calls))])


async def accept(previous: Checked | None, submitted: WrittenDocument) -> Checked:
    """The writer's checks, reduced to one rule: a bullet that says "bad" is rejected."""
    new = merged(previous.doc, submitted, {r.slot for r in previous.rejected}) if previous else submitted
    bad = [Rejection(s, ("bad",), Claim(t, i)) for s, t, i in nodes(new) if "bad" in t]
    return Checked(new, {s: Claim(t, i) for s, t, i in nodes(new) if "bad" not in t}, bad)


def write(*script) -> tuple[Checked | None, Scripted]:
    model = Scripted(script=list(script))
    try:
        return asyncio.run(GraphDocumentWriter(model).write(BRIEF, accept)), model
    except LLMUnavailable:
        return None, model


def test_a_document_that_passes_is_one_call() -> None:
    checked, model = write(doc("ok", "fine"))
    assert checked and not checked.rejected and model.calls == 1


def test_a_rejected_text_is_revised_once_and_accepted_text_stays() -> None:
    checked, model = write(doc("ok", "bad one"), doc("changed", "better"))
    assert model.calls == 2 and checked and not checked.rejected
    assert [t for _, t, _ in nodes(checked.doc)] == ["ok", "better"]  # the first bullet was accepted: the revision's wording for it is ignored


def test_a_revision_that_is_still_rejected_is_the_end_not_a_third_call() -> None:
    checked, model = write(doc("bad", "bad"), doc("bad", "bad"), doc("ok", "ok"))
    assert model.calls == 2 and checked and len(checked.rejected) == 2


def test_a_failed_or_text_only_revision_keeps_the_first_document() -> None:
    for second in (RuntimeError("down"), None):
        checked, model = write(doc("ok", "bad"), second)
        assert model.calls == 2 and checked and [r.slot for r in checked.rejected] == ["bullet:a2"]


def test_without_a_first_document_the_model_is_unavailable() -> None:
    for first in (None, RuntimeError("down")):
        assert write(first)[0] is None


def test_the_tool_reply_lists_each_rejection_with_its_reasons() -> None:
    text = report(Checked(doc("x"), {}, [Rejection("bullet:a1", ("number not in the source: 9",), Claim("x", ("a1",)))]))
    assert "bullet:a1" in text and "number not in the source: 9" in text and "rejected" in text
    assert "Nothing was rejected" in report(Checked(doc("x"), {}, []))


@given(st.lists(st.one_of(st.just(None), st.just("err"), st.lists(st.sampled_from(["ok", "bad"]), min_size=1, max_size=2)), min_size=2, max_size=2))
@settings(max_examples=60, deadline=None)
def test_whatever_the_model_does_there_are_at_most_two_calls_and_no_recursion_error(script) -> None:
    steps = [RuntimeError("x") if s == "err" else (doc(*s) if s else None) for s in script]
    _, model = write(*steps)
    assert model.calls <= 2


@given(st.lists(st.sampled_from(["ok", "bad"]), min_size=1, max_size=2), st.lists(st.text(min_size=1, max_size=8), min_size=1, max_size=2))
def test_merged_never_rewrites_a_slot_that_was_not_rejected(first, second) -> None:
    previous, submitted = doc(*first), doc(*second)
    rejected = {s for s, t, _ in nodes(previous) if t == "bad"}
    before, after = {s: t for s, t, _ in nodes(previous)}, {s: t for s, t, _ in nodes(merged(previous, submitted, rejected))}
    assert all(after[s] == before[s] for s in before if s not in rejected)


@given(st.integers(0, 3), st.booleans(), st.booleans())
def test_next_step_ends_when_nothing_is_rejected_a_revision_was_done_or_the_call_failed(rounds, rejected, failed) -> None:
    checked = Checked(doc("x"), {}, [Rejection("s", ("r",))] if rejected else [])
    assert (next_step(rounds, checked, failed) == "revise") == (rejected and rounds == 0 and not failed)

