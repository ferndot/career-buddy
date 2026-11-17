"""The gate for generated text: bullets are checked like rewordings, prose by `verify_prose`, every claim must cite the brief's facts,
and what was never the writer's to write is dropped."""

from hypothesis import given, strategies as st

from career_buddy.domain.generation import CAPS, Brief, BriefFact, Bullet, Caps, Claim, Generated
from career_buddy.domain.grounding import claims_of, ground, verify_prose

SOURCE = "Cut build times by 60% for Acme Corp using Kubernetes"
FACTS = (BriefFact("a1", "achievement", "Cut build times by 60%", "p1"), BriefFact("p1", "position", "Senior Engineer at Acme Corp"),
         BriefFact("s1", "skill", "Kubernetes"), BriefFact("s2", "skill", "Python"))
BRIEF = Brief("letter", FACTS, company="Acme", role="Engineer")
RESUME = Brief("resume", FACTS)
words = st.text("abcdefghij", min_size=1, max_size=6)


def checked(brief: Brief, written: Generated):
    return ground(brief, claims_of(brief, written))


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


def test_an_unknown_id_is_dropped_from_a_claim_and_a_claim_left_with_none_is_rejected() -> None:
    written = Generated(paragraphs=(Claim("I cut build times by 60% for Acme.", ("a1", "ghost")), Claim("I cut build times by 60%.", ("ghost",)),
                                     Claim("I cut build times by 60%.", ())))
    kept, rejected = checked(BRIEF, written)
    assert kept == {"para:1": Claim("I cut build times by 60% for Acme.", ("a1",))}
    assert [(r.slot, r.reasons) for r in rejected] == [("para:2", ("cites no fact",)), ("para:3", ("cites no fact",))]
    assert rejected[0].claim == Claim("I cut build times by 60%.", ())  # what the repair call is shown


def test_a_bullet_is_for_a_brief_achievement_and_written_once_and_the_rest_is_dropped_not_rejected() -> None:
    written = Generated(bullets=(Bullet("ghost", "Made things"), Bullet("p1", "Held a job"), Bullet("a1", "Reduced build times by 60%"),
                                 Bullet("a1", "Reduced build times by 99%")))
    kept, rejected = checked(RESUME, written)
    assert kept == {"bullet:a1": Claim("Reduced build times by 60%", ("a1",))} and rejected == []


def test_a_bullet_with_an_invented_number_is_rejected_with_the_reason() -> None:
    kept, rejected = checked(RESUME, Generated(bullets=(Bullet("a1", "Reduced build times by 99%"),)))
    assert kept == {} and rejected[0].slot == "bullet:a1" and rejected[0].reasons[0].startswith("number not in the source: 99")


def test_skills_are_the_briefs_own_in_the_writers_order_and_unknown_ones_are_dropped() -> None:
    kept, rejected = checked(RESUME, Generated(skill_ids=("s2", "ghost", "s1", "s2")))
    assert kept == {"skills": Claim("Python, Kubernetes", ("s2", "s1"))} and rejected == []


def test_pinned_slots_are_dropped() -> None:
    pinned = Brief("resume", FACTS, pinned=frozenset({"summary", "bullet:a1", "skills"}))
    written = Generated(Claim("Engineer.", ("a1",)), (Bullet("a1", "Cut build times by 60%"),), ("s1",))
    assert claims_of(pinned, written) == {}
    assert claims_of(Brief("letter", FACTS, pinned=frozenset({"para:2"})), Generated(paragraphs=(Claim("a"), Claim("b"), Claim("c")))).keys() == {"para:1", "para:3"}


def test_banned_markers_are_cleaned_not_rejected_and_only_the_kinds_own_parts_count() -> None:
    kept, rejected = checked(BRIEF, Generated(summary=Claim("ignored", ("a1",)), bullets=(Bullet("a1", "x"),), skill_ids=("s1",),
                                              paragraphs=(Claim("I cut build times by 60%​.", ("a1",)),)))
    assert kept == {"para:1": Claim("I cut build times by 60%.", ("a1",))} and rejected == []


@st.composite
def resumes(draw) -> tuple[Brief, Generated]:
    positions = [f"p{n}" for n in range(draw(st.integers(1, 3)))]
    achievements = [BriefFact(f"a{n}", "achievement", draw(words), draw(st.sampled_from(positions))) for n in range(draw(st.integers(0, 8)))]
    skills = [BriefFact(f"s{n}", "skill", draw(words)) for n in range(draw(st.integers(0, 6)))]
    brief = Brief("resume", (*achievements, *skills), caps=Caps(1, draw(st.integers(1, 4)), draw(st.integers(1, 4))),
                  pinned=frozenset(draw(st.lists(st.sampled_from(["summary", "skills", "bullet:a0", "bullet:a1"]), max_size=3))))
    some_id = st.sampled_from(["a0", "a1", "a2", "a9", "s0", "s1", "s9", "p0"])
    written = Generated(Claim(draw(words), tuple(draw(st.lists(some_id, max_size=3)))) if draw(st.booleans()) else None,
                        tuple(Bullet(draw(some_id), draw(words)) for _ in range(draw(st.integers(0, 12)))),
                        tuple(draw(st.lists(some_id, max_size=10))))
    return brief, written


@given(resumes())
def test_whatever_the_writer_says_only_the_briefs_facts_appear_within_the_caps_and_never_a_pinned_slot(case: tuple[Brief, Generated]) -> None:
    brief, written = case
    claims = claims_of(brief, written)
    allowed = {f.id for f in brief.facts}
    position = {f.id: f.position_id for f in brief.facts if f.kind == "achievement"}
    assert not claims.keys() & brief.pinned
    bullets = [slot.removeprefix("bullet:") for slot in claims if slot.startswith("bullet:")]
    assert set(bullets) <= position.keys()  # an unknown id, or a fact that is not an achievement, never becomes a bullet
    assert all(sum(position[b] == p for b in bullets) <= brief.caps.bullets for p in set(position.values()))
    if "skills" in claims:
        assert set(claims["skills"].fact_ids) <= {f.id for f in brief.facts if f.kind == "skill"} and len(claims["skills"].fact_ids) <= brief.caps.skills
    kept, _ = ground(brief, claims)
    assert all(set(c.fact_ids) <= allowed for c in kept.values())


def test_the_caps_follow_the_length_setting() -> None:
    assert [(c.pages, c.bullets, c.skills) for c in CAPS.values()] == [(1, 3, 10), (2, 5, 15), (3, 7, 20)]
