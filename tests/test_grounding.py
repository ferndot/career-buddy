"""The gate for generated text: bullets are checked like rewordings, prose by `verify_prose`, every claim must cite the brief's facts,
and what was never the writer's to write is dropped."""

from hypothesis import given, strategies as st

from career_buddy.domain.generation import CAPS, Brief, BriefFact, Claim
from career_buddy.domain.grounding import claims_of, ground, verify_prose
from career_buddy.domain.written import LETTER, Bullet, Item, Section, WrittenDocument, nodes, texts, validated

SOURCE = "Cut build times by 60% for Acme Corp using Kubernetes"
FACTS = (BriefFact("a1", "achievement", "Cut build times by 60%", "p1"), BriefFact("p1", "position", "Senior Engineer at Acme Corp"),
         BriefFact("s1", "skill", "Kubernetes"), BriefFact("s2", "skill", "Python"))
words = st.text("abcdefghij", min_size=1, max_size=6)


@given(st.lists(words, min_size=1, max_size=12), st.randoms())
def test_prose_made_of_the_sources_own_words_passes_in_any_order(source_words: list[str], rnd) -> None:
    mixed = list(source_words)
    rnd.shuffle(mixed)
    assert verify_prose(" ".join(source_words), " ".join(mixed)) == []


@given(st.lists(words, min_size=1, max_size=8), st.integers(0, 99999))
def test_a_number_the_source_lacks_is_always_a_reason(source_words: list[str], number: int) -> None:
    source = " ".join(source_words)
    assert any(r.startswith("number") for r in verify_prose(source, f"{source} {number + 100000}"))


def test_i_and_the_first_word_of_every_sentence_are_not_names_but_a_new_name_mid_sentence_is() -> None:
    assert verify_prose(SOURCE, "I cut build times. Then I moved on. The work paid off.") == []
    assert verify_prose(SOURCE, "I cut build times at Globex.") == ["new term not in the source: Globex"]
    assert verify_prose(SOURCE, "I used Terraform.") == ["new term not in the source: Terraform"]  # a tool the facts lack


def test_the_company_the_role_and_known_skills_may_be_named() -> None:
    assert verify_prose(SOURCE, "I want to join Initech as a Lead.", known=["Initech", "Lead"]) == []


def test_a_job_term_the_profile_lacks_is_a_reason_and_so_is_runaway_length() -> None:
    assert verify_prose(SOURCE, "I cut build times with terraform.", missing=["terraform"])[0].startswith("missing job term")
    assert verify_prose("Cut times", "I cut times. " * 80) == ["too long for the facts it cites"]


def doc(*sections: Section) -> WrittenDocument:
    return WrittenDocument(sections=sections)


def letter(*paragraphs: Item, pinned: frozenset[str] = frozenset()) -> tuple[Brief, WrittenDocument]:
    brief = Brief("letter", FACTS, company="Acme", role="Engineer", pinned=pinned, sections=(LETTER,))
    return brief, validated(brief, doc(Section(key=LETTER, items=paragraphs)))


def resume(*sections: Section, pinned: frozenset[str] = frozenset()) -> tuple[Brief, WrittenDocument]:
    brief = Brief("resume", FACTS, pinned=pinned, sections=("summary", "experience", "skills", "education"))
    return brief, validated(brief, doc(*sections))


def experience(*bullets: Bullet) -> Section:
    return Section(key="experience", items=(Item(position_id="p1", bullets=bullets),))


def test_an_unknown_id_is_dropped_from_a_claim_and_a_claim_left_with_none_is_rejected() -> None:
    brief, written = letter(Item(text="I cut build times by 60% for Acme.", fact_ids=("a1", "ghost")), Item(text="I cut build times by 60%.", fact_ids=("ghost",)),
                            Item(text="I cut build times by 60%."))
    kept, rejected = ground(brief, claims_of(brief, written))
    assert kept == {"para:1": Claim("I cut build times by 60% for Acme.", ("a1",))}
    assert [(r.slot, r.reasons) for r in rejected] == [("para:2", ("cites no fact",)), ("para:3", ("cites no fact",))]
    assert rejected[0].claim == Claim("I cut build times by 60%.", ())  # what the repair call is shown


def test_a_bullet_may_join_achievements_and_is_checked_against_all_it_cites() -> None:
    brief = Brief("resume", (*FACTS, BriefFact("a2", "achievement", "Migrated 40 services", "p1")), sections=("experience",))
    written = validated(brief, doc(experience(Bullet(text="Cut build times by 60% and migrated 40 services", fact_ids=("a1", "a2")),
                                              Bullet(text="Cut build times by 60% and migrated 40 services", fact_ids=("a1",)))))
    kept, rejected = ground(brief, claims_of(brief, written))
    assert list(kept) == ["bullet:a1"] and [r.slot for r in rejected] == ["bullet:a1#2"]  # the same wording rests on two facts in one bullet only; on one fact it adds a number
    assert rejected[0].reasons[0].startswith("number not in the source: 40")


def test_a_bullet_for_a_fact_that_is_not_an_achievement_of_its_position_is_dropped_not_rejected() -> None:
    _, written = resume(experience(Bullet(text="Made things", fact_ids=("ghost",)), Bullet(text="Held a job", fact_ids=("p1",)), Bullet(text="Reduced build times by 60%", fact_ids=("a1",))))
    assert texts(written) == {"bullet:a1": "Reduced build times by 60%"}


def test_a_bullet_with_an_invented_number_is_rejected_with_the_reason() -> None:
    brief, written = resume(experience(Bullet(text="Reduced build times by 99%", fact_ids=("a1",))))
    kept, rejected = ground(brief, claims_of(brief, written))
    assert kept == {} and rejected[0].slot == "bullet:a1" and rejected[0].reasons[0].startswith("number not in the source: 99")


def test_a_skills_line_may_group_but_only_the_skills_it_cites_and_an_education_line_keeps_its_degree() -> None:
    brief = Brief("resume", (*FACTS, BriefFact("e1", "education", "BSc Computer Science, University of Lisbon")), sections=("skills", "education"))
    written = validated(brief, doc(Section(key="skills", items=(Item(text="Tools: Kubernetes, Python", fact_ids=("s1", "s2")), Item(text="Tools: Terraform", fact_ids=("s1",)))),
                                   Section(key="education", items=(Item(text="BSc Computer Science", fact_ids=("e1",)),))))
    kept, rejected = ground(brief, claims_of(brief, written), skills=["Kubernetes", "Python"], protected=["University of Lisbon"])
    assert list(kept) == ["skills"] and [r.slot for r in rejected] == ["skills#2", "edu:e1"]
    assert "Terraform" in rejected[0].reasons[0] and rejected[1].reasons == ("protected text changed: University of Lisbon",)


def test_pinned_slots_have_no_claim() -> None:
    brief, written = resume(Section(key="summary", items=(Item(text="Engineer.", fact_ids=("a1",)),)), experience(Bullet(text="Cut build times by 60%", fact_ids=("a1",))),
                            pinned=frozenset({"summary", "bullet:a1"}))
    assert claims_of(brief, written) == {} and nodes(written)[0][:2] == ("summary", "")
    brief, written = letter(Item(text="a", fact_ids=("a1",)), Item(text="b", fact_ids=("a1",)), Item(text="c", fact_ids=("a1",)), pinned=frozenset({"para:2"}))
    assert claims_of(brief, written).keys() == {"para:1", "para:3"}


def test_banned_markers_are_cleaned_not_rejected() -> None:
    brief, written = letter(Item(text="I cut build times by 60%​.", fact_ids=("a1",)))
    kept, rejected = ground(brief, claims_of(brief, written))
    assert kept == {"para:1": Claim("I cut build times by 60%.", ("a1",))} and rejected == []


def test_the_caps_follow_the_length_setting() -> None:
    assert [(c.pages, c.bullets, c.skills) for c in CAPS.values()] == [(1, 3, 10), (2, 5, 15), (3, 7, 20)]
