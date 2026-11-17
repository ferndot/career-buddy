"""The document a writer writes: its schema, the rules that make it fit to print (template order, caps, citations, pinned slots) and how a
written document becomes a layout whose slots the saved document and the user's edits are keyed by."""

import json

import pytest
from hypothesis import given, strategies as st
from pydantic import ValidationError

from career_buddy.adapters.inference.document_writer import payload, system_prompt
from career_buddy.adapters.outputs.render_html import stored_html
from career_buddy.adapters.readers.html_document import read_slots
from career_buddy.adapters.outputs.render_markdown import MarkdownRenderer
from career_buddy.adapters.outputs.render_text import TextRenderer
from career_buddy.domain.document import Document, Line, Style
from career_buddy.domain.generation import Brief, BriefFact, Caps
from career_buddy.domain.templates import RESUME_MODERN, get_template
from career_buddy.domain.writing_rules import DEFAULT_RULES
from career_buddy.domain.written import LETTER, Bullet, Item, Section, WrittenDocument, mapped, nodes, numbered, texts, to_document, validated

MODERN = tuple(k for k, _ in RESUME_MODERN.sections)
FACTS = (BriefFact("p1", "position", "Senior Engineer at Acme Corp", started="2019", finished="2023"),
         BriefFact("a1", "achievement", "Cut build times by 60%", "p1"), BriefFact("a2", "achievement", "Migrated 40 services to Kubernetes", "p1"),
         BriefFact("a3", "achievement", "Built ETL jobs", "p1"), BriefFact("a4", "achievement", "Moved the CI to GitHub Actions", "p1"),
         BriefFact("p2", "position", "Engineer at Globex"), BriefFact("b1", "achievement", "Wrote the billing API", "p2"),
         BriefFact("s1", "skill", "Python"), BriefFact("s2", "skill", "Go"), BriefFact("s3", "skill", "Kubernetes"),
         BriefFact("e1", "education", "BSc Computer Science, University of Lisbon"))
BRIEF = Brief("resume", FACTS, sections=MODERN, caps=Caps(1, 3, 2))


def bullet(text: str, *ids: str) -> Bullet:
    return Bullet(text=text, fact_ids=ids)


def doc(*sections: Section) -> WrittenDocument:
    return WrittenDocument(sections=sections)


# --- the schema ---

def test_the_answer_must_have_sections_and_typed_texts() -> None:
    assert WrittenDocument.model_validate({"sections": [{"key": "summary", "items": [{"text": "x", "fact_ids": ["a1"]}]}]}).sections[0].items[0].fact_ids == ("a1",)
    for bad in ({}, {"sections": [{"items": []}]}, {"sections": [{"key": "summary", "items": [{"text": 5}]}]}, {"sections": [{"key": "summary", "items": [{"fact_ids": "a1"}]}]}):
        with pytest.raises(ValidationError):
            WrittenDocument.model_validate(bad)


def test_the_schema_the_model_is_shown_has_no_slot_field() -> None:
    assert "slot" not in json.dumps(WrittenDocument.model_json_schema())  # slot ids are ours to give


# --- what the model is sent ---

def test_the_context_has_facts_sections_posting_directions_and_the_system_message_has_the_template_and_length() -> None:
    brief = Brief("resume", FACTS, ("Kubernetes",), ("Terraform",), "Acme", "Engineer", "Stress Kubernetes", "Platform engineer", Caps(2, 5, 15),
                  frozenset({"bullet:a1"}), "Compact modern resume.", MODERN)
    sent = json.loads(payload(brief, brief.facts))
    assert sent["sections"] == ["summary", "experience", "education", "skills"] and sent["directions"] == "Stress Kubernetes" and sent["posting"] == "Platform engineer"
    assert sent["pinned"] == ["bullet:a1"] and sent["missing_terms"] == ["Terraform"] and sent["job_terms"] == ["Kubernetes"]
    assert set(sent["facts"]) == {"positions", "skills", "education"} and "caps" not in sent and "template_instructions" not in sent
    system = system_prompt(brief)
    assert "summary, experience, education, skills" in system and "Template instructions: Compact modern resume." in system
    assert "2 pages long. At most 5 bullets for each position and 15 skills" in system and "Answer with one JSON object" in system
    letter = system_prompt(Brief("letter", FACTS, sections=(LETTER,), template_instructions="Three short paragraphs."))
    assert "Template: write these sections, in this order: body." in letter and "Length:" not in letter and "cover letter" in letter and "Three short paragraphs." in letter
    repair = system_prompt(brief, repair=True)
    assert "were rejected" in repair and "Answer with one JSON object" not in repair


def test_the_writer_reads_each_position_with_its_achievements_together_and_is_not_told_one_item_per_fact() -> None:
    sent = json.loads(payload(BRIEF, BRIEF.facts))["facts"]
    first = sent["positions"][0]
    assert first["id"] == "p1" and [a["id"] for a in first["achievements"]] == ["a1", "a2", "a3", "a4"]
    assert [s["id"] for s in sent["skills"]] == ["s1", "s2", "s3"] and sent["education"][0]["id"] == "e1"
    resume, letter = system_prompt(BRIEF), system_prompt(Brief("letter", FACTS, sections=(LETTER,)))
    assert "one bullet per achievement is not the goal" in resume and "never write one item per fact" in resume and "not a paragraph per fact" in letter


def test_the_general_rules_for_the_kind_are_in_the_system_message_and_come_from_the_brief() -> None:
    resume = system_prompt(Brief("resume", FACTS, sections=MODERN, rules=DEFAULT_RULES["resume"]))
    letter = system_prompt(Brief("letter", FACTS, sections=(LETTER,), rules=DEFAULT_RULES["letter"]))
    assert "General rules for a resume" in resume and "3 to 6 bullets" in resume and "vary the verbs" in resume and "250 to 400 words" not in resume
    assert "General rules for a letter" in letter and "250 to 400 words" in letter and "Dear Sir or Madam" in letter and "3 to 6 bullets" not in letter
    assert "Use only the given facts" in resume and "Use only the given facts" in letter  # the grounding rules stay
    own = system_prompt(Brief("resume", FACTS, sections=MODERN, rules=("Keep every bullet under ten words.",)))
    assert "Keep every bullet under ten words." in own and "3 to 6 bullets" not in own  # a person's own set replaces the default
    assert "General rules" not in system_prompt(Brief("resume", FACTS, sections=MODERN))
    assert "General rules" not in system_prompt(Brief("resume", FACTS, rules=DEFAULT_RULES["resume"]), repair=True)
    assert "CONDENSE" in resume and "SEPARATE" in resume and "HYBRID" in resume and "CONDENSE" not in letter


# --- what is fit to print ---

def test_sections_come_back_in_the_templates_order_once_and_only_the_templates() -> None:
    written = validated(BRIEF, doc(Section(key="skills", items=(Item(text="Python", fact_ids=("s1",)),)), Section(key="cover", items=(Item(text="no", fact_ids=("a1",)),)),
                                   Section(key="summary", items=(Item(text="One.", fact_ids=("a1",)), Item(text="Two.", fact_ids=("a1",)))),
                                   Section(key="summary", items=(Item(text="Again.", fact_ids=("a1",)),))))
    assert [s.key for s in written.sections] == ["summary", "skills"]
    assert texts(written) == {"summary": "One.", "skills": "Python"}  # a summary is one item; a section's first answer stands


def test_a_position_gets_the_bullets_the_writer_chose_up_to_the_cap_each_resting_on_its_own_achievements() -> None:
    written = validated(BRIEF, doc(Section(key="experience", items=(
        Item(position_id="p2", bullets=(bullet("Wrote the billing API", "b1"), bullet("Wrote the Acme thing", "a1"))),  # a1 is p1's: no bullet of p2
        Item(position_id="p1", bullets=(bullet("Cut build times by 60%", "s1", "a1"), bullet("Migrated services", "a2", "a3"), bullet("Built ETL jobs", "a3"),
                                        bullet("Moved the CI", "a4"), bullet("  ", "a1"))),
        Item(position_id="ghost", bullets=(bullet("x", "a1"),))))))
    assert [(i.position_id, [(b.slot, b.fact_ids) for b in i.bullets]) for i in written.sections[0].items] == [
        ("p1", [("bullet:a1", ("a1", "s1")), ("bullet:a2", ("a2", "a3")), ("bullet:a3", ("a3",))]),  # the position's own achievement first, then the rest; the cap is 3
        ("p2", [("bullet:b1", ("b1",))])]  # the brief's order, not the writer's


SAME_COMPANY = (BriefFact("p1", "position", "Senior Analyst at Acme", started="2021", finished="2024"), BriefFact("a1", "achievement", "Led the forecasting model", "p1"),
                BriefFact("a2", "achievement", "Cut report time by half", "p1"),
                BriefFact("p3", "position", "Analyst at Acme", started="2017", finished="2021"), BriefFact("c1", "achievement", "Built the weekly sales report", "p3"),
                BriefFact("c2", "achievement", "Cleaned the customer data", "p3"))
SAME = Brief("resume", SAME_COMPANY, sections=("experience",), caps=Caps(1, 3, 5))


def experience(*items: Item) -> WrittenDocument:
    return doc(Section(key="experience", items=items))


def test_positions_at_one_company_can_be_condensed_into_one_item_with_one_set_of_bullets() -> None:
    written = validated(SAME, experience(Item(position_id="p3", also=("p1", "ghost", "p3"), bullets=(
        bullet("Led the forecasting model", "a1"), bullet("Built the weekly sales report", "c1"), bullet("Cleaned the data", "c2"), bullet("Cut report time", "a2"), bullet("x", "ghost")))))
    [item] = written.sections[0].items
    assert (item.position_id, item.also) == ("p1", ("p3",))  # the newest leads, whatever order the writer named them in
    assert [(b.slot, b.fact_ids) for b in item.bullets] == [("bullet:a1", ("a1",)), ("bullet:c1", ("c1",)), ("bullet:c2", ("c2",)), ("bullet:a2", ("a2",))]  # the cap of 3, plus one for the second title


def test_positions_the_writer_keeps_apart_stay_separate_items_with_their_own_bullets() -> None:
    written = validated(SAME, experience(Item(position_id="p3", bullets=(bullet("Built the report", "c1"), bullet("Not mine", "a1"))), Item(position_id="p1", bullets=(bullet("Led it", "a1"),))))
    assert [(i.position_id, i.also, [b.fact_ids for b in i.bullets]) for i in written.sections[0].items] == [("p1", (), [("a1",)]), ("p3", (), [("c1",)])]


def test_a_position_belongs_to_one_item_only() -> None:
    written = validated(SAME, experience(Item(position_id="p1", also=("p3",), bullets=(bullet("Led it", "a1"),)), Item(position_id="p3", bullets=(bullet("Built the report", "c1"),))))
    assert [(i.position_id, i.also, len(i.bullets)) for i in written.sections[0].items] == [("p1", ("p3",), 1)]  # the second item is p3's again: dropped


def test_a_pinned_bullet_of_a_condensed_position_goes_to_its_item() -> None:
    brief = Brief("resume", SAME_COMPANY, sections=("experience",), caps=Caps(1, 3, 5), pinned=frozenset({"bullet:c2"}))
    written = validated(brief, experience(Item(position_id="p1", also=("p3",), bullets=(bullet("Led it", "a1"),))))
    assert [(i.position_id, [b.slot for b in i.bullets]) for i in written.sections[0].items] == [("p1", ["bullet:a1", "bullet:c2"])]


def test_a_condensed_item_prints_a_heading_line_for_each_title_then_its_bullets_in_every_format() -> None:
    written = validated(SAME, experience(Item(position_id="p1", also=("p3",), bullets=(bullet("Led it", "a1"), bullet("Built the report", "c1")))))
    headings = {"p1": "Senior Analyst, Acme (2021 - 2024)", "p3": "Analyst, Acme (2017 - 2021)"}
    printed = to_document(Document(Line("Jane", "person", field="title")), RESUME_MODERN, written, headings)
    entries = printed.sections[0].entries
    assert [(e.heading.text, [b.text for b in e.bullets]) for e in entries if e.heading] == [(headings["p1"], []), (headings["p3"], ["Led it", "Built the report"])]
    html = stored_html(printed, get_template("resume-modern").layout)
    assert [s.id for s in read_slots(html) if s.id != "name"] == ["heading:p1", "heading:p3", "bullet:a1", "bullet:c1"]
    for rendered in (TextRenderer().render(printed, Style()), MarkdownRenderer().render(printed, Style())):
        out = rendered.decode()
        assert out.index("Senior Analyst") < out.index("Analyst, Acme (2017") < out.index("Led it")


def test_the_same_fact_twice_gets_a_suffix_and_a_unknown_citation_is_dropped() -> None:
    written = validated(BRIEF, doc(Section(key="experience", items=(Item(position_id="p1", bullets=(bullet("Cut build times", "a1", "ghost"), bullet("Cut build times again", "a1"))),))))
    assert [b.slot for b in written.sections[0].items[0].bullets] == ["bullet:a1", "bullet:a1#2"] and written.sections[0].items[0].bullets[0].fact_ids == ("a1",)


def test_skills_and_education_lines_are_kept_to_the_cap_and_to_their_facts() -> None:
    written = validated(BRIEF, doc(
        Section(key="skills", items=(Item(text="Languages: Python, Go", fact_ids=("s1", "s2")), Item(text="Kubernetes", fact_ids=("s3",)))),  # a third skill passes the cap of 2
        Section(key="education", items=(Item(text="BSc Computer Science, University of Lisbon", fact_ids=("s1", "e1")), Item(text="no fact", fact_ids=("s1",))))))
    assert texts(written) == {"skills": "Languages: Python, Go", "edu:e1": "BSc Computer Science, University of Lisbon"}
    assert written.sections[0].items[0].fact_ids == ("e1", "s1")


def test_a_letter_is_paragraphs_in_one_body_section() -> None:
    brief = Brief("letter", FACTS, sections=(LETTER,))
    written = validated(brief, doc(Section(key=LETTER, items=tuple(Item(text=f"P{n}", fact_ids=("a1",)) for n in range(9))), Section(key="summary", items=(Item(text="no"),))))
    assert list(texts(written)) == [f"para:{n}" for n in range(1, 7)]


# --- the person's own words ---

def test_a_pinned_slot_is_blanked_if_the_writer_wrote_it_and_added_if_it_did_not() -> None:
    brief = Brief("resume", FACTS, sections=MODERN, caps=Caps(1, 3, 10), pinned=frozenset({"bullet:a1", "bullet:b1", "summary", "edu:e1", "bullet:zzz"}))
    written = validated(brief, doc(Section(key="experience", items=(Item(position_id="p1", bullets=(bullet("Cut build times", "a1"), bullet("Built ETL jobs", "a3"))),))))
    assert [(slot, text) for slot, text, _ in nodes(written)] == [("summary", ""), ("bullet:a1", ""), ("bullet:a3", "Built ETL jobs"), ("bullet:b1", ""), ("edu:e1", "")]
    assert [s.key for s in written.sections] == ["summary", "experience", "education"]  # placed in the template's order


def test_pinned_letter_paragraphs_keep_their_numbers() -> None:
    brief = Brief("letter", FACTS, sections=(LETTER,), pinned=frozenset({"para:3"}))
    assert [slot for slot, _, _ in nodes(validated(brief, doc(Section(key=LETTER, items=(Item(text="One", fact_ids=("a1",)),)))))] == ["para:1", "para:2", "para:3"]


# --- a property of the validator ---

ids = st.sampled_from([f.id for f in FACTS] + ["ghost", "a9"])
words = st.text("abc xyz", max_size=8)
bullets_ = st.builds(Bullet, text=words, fact_ids=st.lists(ids, max_size=4).map(tuple))
items = st.builds(Item, text=words, fact_ids=st.lists(ids, max_size=4).map(tuple), position_id=st.sampled_from(["p1", "p2", "ghost", "a1", ""]),
                  also=st.lists(st.sampled_from(["p1", "p2", "ghost"]), max_size=2).map(tuple),
                  bullets=st.lists(bullets_, max_size=7).map(tuple))
sections = st.builds(Section, key=st.sampled_from([*MODERN, LETTER, "x"]), items=st.lists(items, max_size=4).map(tuple))
briefs = st.builds(lambda b, s, pins: Brief("resume", FACTS, sections=MODERN, caps=Caps(1, b, s), pinned=frozenset(pins)),
                   st.integers(1, 4), st.integers(1, 3), st.lists(st.sampled_from(["summary", "skills", "bullet:a1", "bullet:b1", "edu:e1", "para:2", "bullet:s1"]), max_size=4))


@given(briefs, st.lists(sections, max_size=8))
def test_whatever_the_writer_answers_the_document_fits_the_template_the_facts_and_the_caps(brief: Brief, answer: list[Section]) -> None:
    written = validated(brief, WrittenDocument(sections=tuple(answer)))
    known = {f.id: f for f in FACTS}
    keys = [s.key for s in written.sections]
    assert keys == [k for k in brief.sections if k in keys] and len(set(keys)) == len(keys)  # the template's order, each once, nothing else
    slots = [slot for slot, _, _ in nodes(written)]
    assert len(set(slots)) == len(slots)  # one id per text
    assert all(text == "" for slot, text, _ in nodes(written) if slot in brief.pinned)  # a pinned slot is the person's, not the writer's
    for s in written.sections:
        assert all(known.get(i) for it in s.items for i in (*it.fact_ids, *(x for b in it.bullets for x in b.fact_ids)))  # every cited id is a fact of the brief
        if s.key == "experience":
            held = [p for it in s.items for p in (it.position_id, *it.also)]
            assert len(set(held)) == len(held) and all(known[p].kind == "position" for p in held)  # a position is in one item only
            for it in s.items:
                free = [b for b in it.bullets if b.text]  # a pinned placeholder has no text
                assert len(free) <= brief.caps.bullets + len(it.also)
                assert all(b.fact_ids and known[b.fact_ids[0]].kind == "achievement" and known[b.fact_ids[0]].position_id in (it.position_id, *it.also) for b in it.bullets)
        if s.key == "skills":
            assert len({i for it in s.items for i in it.fact_ids if known[i].kind == "skill"}) <= brief.caps.skills
        if s.key == "education":
            assert all(it.fact_ids and known[it.fact_ids[0]].kind == "education" for it in s.items)
    assert numbered(written) == written and mapped(written, lambda slot, text, ids: (text, ids)) == written  # numbering and an identity edit change nothing


# --- from sections to a layout ---

def test_a_written_document_becomes_a_layout_whose_slots_are_the_sections_and_whose_text_is_not_stored() -> None:
    written = validated(BRIEF, doc(Section(key="summary", items=(Item(text="Platform engineer.", fact_ids=("a1",)),)), Section(key="experience", items=(
        Item(position_id="p1", bullets=(bullet("Cut build times by 60%", "a1"), bullet("Moved services", "a2", "a3"))),)),
        Section(key="education", items=(Item(text="BSc", fact_ids=("e1",)),))))
    base = Document(Line("Jane", "person", field="title"), (Line("Lisbon", "person", field="location"),))
    printed = to_document(base, RESUME_MODERN, written, {"p1": "Senior Engineer, Acme Corp (2019 - 2023)"})
    assert [s.title for s in printed.sections] == ["Summary", "Experience", "Education"] and printed.layout == base.layout
    html = stored_html(printed, get_template("resume-modern").layout)
    slots = {s.id: s for s in read_slots(html)}
    assert [s for s in slots if s not in ("name", "location")] == ["summary", "heading:p1", "bullet:a1", "bullet:a2", "edu:e1"]
    assert slots["bullet:a2"].fact_ids == ("a2", "a3") and slots["bullet:a2"].field == "title" and "Moved" not in html and "Platform" not in html


def test_a_clients_sections_are_not_trusted_when_they_are_laid_out() -> None:
    base = Document(Line("Jane", "person", field="title"))
    wild = doc(Section(key="nope", items=(Item(text="x", fact_ids=("a1",)),)), Section(key=LETTER, items=(Item(text="x"),)),
               Section(key="experience", items=(Item(position_id="ghost", bullets=(bullet("x", "a1"),)), Item(position_id="p1", bullets=(Bullet(text="no ids"),)))),
               Section(key="education", items=(Item(text="no ids"),)))
    printed = to_document(base, RESUME_MODERN, wild, {"p1": "Engineer"})
    assert [(s.title, [e.heading for e in s.entries], [list(e.bullets) for e in s.entries]) for s in printed.sections] == [("Experience", [Line("Engineer", "p1")], [[]]), ("Education", [None], [[]])]
