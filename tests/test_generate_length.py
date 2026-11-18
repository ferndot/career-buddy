"""The length and coverage checks of a generated resume, over HTTP with a fixed page counter standing in for the browser: a relevant role the
writer left out, a resume that prints too long, the one revision and its bounds, and no browser."""

from pathlib import Path

from career_buddy.application.ports import RendererUnavailable
from career_buddy.domain.coverage import Pages
from test_generate_api import CUT, ETL, LETTER, MIGRATED, RESUME, Model, experience, find, generate, good, ids, letter_answer, open_client, section

class Counter:
    """A fixed page counter standing in for the browser: its answers in order, the last repeating. An exception is raised instead of answered."""

    def __init__(self, *answers) -> None:
        self.answers, self.calls = list(answers), 0

    def pages(self, doc, style):
        answer = self.answers[min(self.calls, len(self.answers) - 1)]
        self.calls += 1
        if isinstance(answer, Exception):
            raise answer
        return answer


def test_a_relevant_role_the_writer_left_out_is_reported_and_added_by_the_revision(tmp_path: Path) -> None:
    def first(p):
        return {"sections": [experience(p, (find(p, CUT), "Reduced build times by 60%"), (find(p, MIGRATED), "Moved 40 services to Kubernetes"))]}

    model = Model(first, repair=lambda p: {"sections": [experience(p, (find(p, ETL), "Built ETL jobs"))]})
    counter = Counter(Pages(1, 0.9, 50))
    with open_client(tmp_path, model, counter) as client:
        known = ids(client)
        draft = generate(client, RESUME)
    assert len(model.payloads) == 2 and counter.calls == 2
    assert "Engineer at Globex" in model.replies[0] and known[ETL] in model.replies[0] and "missing" in model.replies[0]
    assert set(draft["slots"]) == {f"bullet:{known[CUT]}", f"bullet:{known[MIGRATED]}", f"bullet:{known[ETL]}"}  # the accepted bullets stay, the new one is added
    assert draft["pages"] == {"count": 1, "limit": 2}


def test_a_resume_that_prints_too_long_is_told_the_lines_over_and_what_it_leaves_out_is_removed(tmp_path: Path) -> None:
    def shorter(p):
        return {"sections": [experience(p, (find(p, CUT), "A different wording that is ignored"), (find(p, MIGRATED), "Moved 40 services to Kubernetes"))]}

    model = Model(good, repair=shorter)
    with open_client(tmp_path, model, Counter(Pages(2, 0.5, 40), Pages(1, 0.9, 40))) as client:
        known = ids(client)
        draft = generate(client, {**RESUME, "resume_pages": 1})
    assert "about 20 lines over" in model.replies[0]
    assert set(draft["slots"]) >= {f"bullet:{known[CUT]}", f"bullet:{known[MIGRATED]}"} and f"bullet:{known[ETL]}" not in draft["slots"]
    assert draft["slots"][f"bullet:{known[CUT]}"] == "Reduced build times by 60%"  # accepted text is not rewritten
    assert draft["pages"] == {"count": 1, "limit": 1}


def test_a_revision_that_is_not_over_length_cannot_drop_a_bullet(tmp_path: Path) -> None:
    def first(p):
        return {"sections": [experience(p, (find(p, CUT), "Reduced build times by 60%"), (find(p, MIGRATED), "Moved 40 services to Kubernetes"))]}

    model = Model(first, repair=lambda p: {"sections": [section("experience")]})  # the revision sends nothing
    with open_client(tmp_path, model, Counter(Pages(1, 0.9, 40))) as client:
        known = ids(client)
        draft = generate(client, RESUME)
    assert len(model.payloads) == 2 and "missing" in model.replies[0]
    assert set(draft["slots"]) == {f"bullet:{known[CUT]}", f"bullet:{known[MIGRATED]}"}  # nothing was dropped, nothing invented


def test_the_loop_ends_after_one_revision_however_long_the_resume_still_prints(tmp_path: Path) -> None:
    model = Model(good, repair=lambda p: good(p))
    counter = Counter(Pages(3, 0.5, 40))
    with open_client(tmp_path, model, counter) as client:
        draft = generate(client, {**RESUME, "resume_pages": 1})
    assert len(model.payloads) == 2 and counter.calls == 2  # one render per model call, never more
    assert draft["pages"] == {"count": 3, "limit": 1}  # the draft is returned as written, with the count so the person sees it


def test_a_resume_that_prints_within_its_pages_with_every_relevant_role_is_one_call(tmp_path: Path) -> None:
    model = Model(good)
    with open_client(tmp_path, model, Counter(Pages(1, 0.9, 40))) as client:
        draft = generate(client, RESUME)
    assert len(model.payloads) == 1 and draft["pages"] == {"count": 1, "limit": 2}


def test_without_a_browser_the_length_check_is_skipped_and_the_draft_still_comes_back(tmp_path: Path) -> None:
    for broken in (RendererUnavailable("no chromium"), RuntimeError("crashed")):
        model = Model(good)
        with open_client(tmp_path / type(broken).__name__, model, Counter(broken)) as client:
            draft = generate(client, RESUME)
        assert len(model.payloads) == 1 and draft["pages"] is None and len(draft["slots"]) == 5


def test_a_letter_is_not_measured(tmp_path: Path) -> None:
    counter = Counter(Pages(9, 1.0, 40))
    with open_client(tmp_path, Model(lambda p: letter_answer(("I am applying for the Engineer role at Acme.", [find(p, "Senior Engineer", "position")]))), counter) as client:
        draft = generate(client, LETTER)
    assert counter.calls == 0 and draft["pages"] is None
