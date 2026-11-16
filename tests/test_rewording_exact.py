"""verify_rewording: the exact reasons it gives, including how it lists several offenders."""

from career_buddy.domain.rewording import verify_rewording

SOURCE = "Cut build times by 60% across the services we ran"


def test_numbers_are_listed_sorted() -> None:
    assert verify_rewording(SOURCE, "Cut build times by 75% across the services we 90", ())[0] == (
        "number not in the source: 75, 90")


def test_new_terms_are_listed_in_order() -> None:
    reasons = verify_rewording(SOURCE, "Cut build times by 60% across the Kafka Spark services we ran", ())
    assert reasons == ["new term not in the source or profile skills: Kafka, Spark"]


def test_a_missing_term_added_as_a_phrase_is_named() -> None:
    reasons = verify_rewording(SOURCE, "Cut build times by 60% across machine learning services we", (),
                               missing=["machine learning"])
    assert reasons == ["missing job term added: machine learning"]


def test_several_missing_terms_are_listed() -> None:
    reasons = verify_rewording(SOURCE, "Cut build times by 60% across deep machine services", (),
                               missing=["deep", "machine"])
    assert reasons == ["missing job term added: deep, machine"]


def test_a_dash_is_the_banned_marker_and_a_flagged_word_before_it_is_ignored() -> None:
    source = "Fixed potential bugs and fast"
    assert verify_rewording(source, "Fixed potential bugs — fast", ()) == ["banned marker: —"]


def test_growth_up_to_exactly_thirty_percent_is_allowed() -> None:
    assert verify_rewording("aaaaaaaaaa", "aaaaaaaaaaaaa", ()) == []
    assert verify_rewording("aaaaaaaaaa", "aaaaaaaaaaaaaa", ()) == ["too long: more than 1.3 times the source"]


def test_lost_protected_texts_are_listed() -> None:
    reasons = verify_rewording("Lead at Acme Corp with a BSc", "Lead at somewhere with a degree", (),
                               protected=["Acme Corp", "BSc"])
    assert reasons == ["protected text changed: Acme Corp, BSc"]
