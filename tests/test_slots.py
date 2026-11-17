"""Slots: the order text is found in, the slot ids, and that a layout read back with the facts says what the template said."""

from hypothesis import given, strategies as st

from career_buddy.adapters.outputs.render_html import stored_html
from career_buddy.adapters.readers.html_document import read_document, read_slots
from career_buddy.domain.document import Line, Origin
from career_buddy.domain.profile import EducationView, PositionView, Profile
from career_buddy.domain.slots import FACT_FIELDS, Slot, fact_texts, layout_overrides, resolve, slot_for
from career_buddy.domain.templates import TEMPLATES, build_document

words = st.text("abcdefghijklmnopqrstuvwxyz ", min_size=1, max_size=12).map(lambda s: " ".join(s.split())).filter(bool)
ids = st.text("0123456789abcdef", min_size=1, max_size=6)


@st.composite
def profiles(draw) -> Profile:
    positions, skills = [], draw(st.lists(words, max_size=4, unique=True))
    for n in range(draw(st.integers(0, 3))):
        found = draw(st.lists(words, max_size=3))
        positions.append(PositionView(draw(words), draw(words | st.just("")), {"started": "2020"} if draw(st.booleans()) else {},
                                      tuple(found), (), f"pos{n}", tuple(f"a{n}_{i}" for i in range(len(found)))))
    education = tuple(EducationView(draw(words), draw(words), {}, f"e{i}") for i in range(draw(st.integers(0, 2))))
    attributes = {k: draw(words) for k in ("location", "headline", "summary") if draw(st.booleans())}
    return Profile(draw(words), attributes, tuple(positions), education, tuple(skills), "p", tuple(f"s{i}" for i in range(len(skills))))


@given(profiles(), st.sampled_from(TEMPLATES))
def test_a_layout_read_back_against_the_facts_says_what_the_template_says(profile: Profile, spec) -> None:
    doc = build_document(profile, spec, {"company": "Acme", "role": "Engineer"})
    html = stored_html(doc)
    texts = resolve(read_slots(html), {}, fact_texts(profile))
    assert read_document(html, texts).lines() == doc.lines()
    assert all(s.placeholder == "" for s in read_slots(html) if s.field in FACT_FIELDS)  # a slot shown from a fact stores no text


@given(st.lists(ids, min_size=1, max_size=5, unique=True), st.dictionaries(ids, words), st.dictionaries(ids, words))
def test_text_is_the_override_then_the_fact_then_the_placeholder(names, overrides, facts) -> None:
    slots = [Slot(f"x:{n}", (n,), "title", "placeholder") for n in names]
    out = resolve(slots, {f"x:{k}": v for k, v in overrides.items()}, {(k, "title"): v for k, v in facts.items()})
    for n in names:
        assert out[f"x:{n}"] == overrides.get(n, facts.get(n, "placeholder"))


@given(words)
def test_a_blank_override_is_not_an_override(text: str) -> None:
    assert resolve([Slot("a", ("f",), "title")], {"a": "  "}, {("f", "title"): text}) == {"a": text}


def test_fixed_wording_never_resolves_from_the_fact_it_carries() -> None:
    taken: set[str] = set()
    greeting = slot_for("paragraph", Line("Dear Team,", "p", Origin.BOILERPLATE, "greeting"), taken)
    assert greeting == Slot("greeting", (), "", "Dear Team,")
    assert resolve([greeting], {}, {("p", "title"): "Jane", ("p", "greeting"): "Jane"}) == {"greeting": "Dear Team,"}


def test_ids_are_stable_and_a_repeated_one_gets_a_suffix() -> None:
    taken: set[str] = set()
    names = [slot_for("bullet", Line("x", "a1", field="title"), taken).id, slot_for("bullet", Line("x", "a1", field="title"), taken).id,
             slot_for("name", Line("Jane", "p", field="title"), taken).id, slot_for("paragraph", Line("Jane", "p", field="title"), taken).id,
             slot_for("paragraph", Line("one"), taken).id, slot_for("paragraph", Line("two"), taken).id,
             slot_for("heading", Line("Job", "j", field="heading"), taken).id, slot_for("bullet", Line("BSc", "e", field="label"), taken).id]
    assert names == ["bullet:a1", "bullet:a1#2", "name", "signature", "para:1", "para:2", "heading:j", "edu:e"]


def test_a_skills_slot_lists_the_skills_that_still_exist() -> None:
    slot = Slot("skills", ("s1", "s2", "s3"), "skills")
    assert resolve([slot], {}, {("s1", "skills"): "Python", ("s3", "skills"): "Go"}) == {"skills": "Python, Go"}


@given(st.dictionaries(ids, words))
def test_a_save_keeps_only_overrides_that_name_a_slot(given_: dict[str, str]) -> None:
    slots = ["name", "bullet:a1", "para:1"]
    kept = layout_overrides({**given_, "a1": "mine", "para:1": "p", "zzz": "orphan"}, slots)
    assert kept["bullet:a1"] == "mine" and kept["para:1"] == "p" and "zzz" not in kept
    assert set(kept) <= set(slots)


def test_a_written_line_brings_its_own_id() -> None:
    taken: set[str] = set()
    ids_ = [slot_for("bullet", Line("x", "a1", field="title", cites=("a1", "a2"), slot="bullet:a1"), taken),
            slot_for("bullet", Line("y", "a1", field="title", cites=("a1",), slot="bullet:a1"), taken)]
    assert [s.id for s in ids_] == ["bullet:a1", "bullet:a1#2"] and ids_[0].fact_ids == ("a1", "a2")  # a repeat is still numbered; the cites are the slot's facts
