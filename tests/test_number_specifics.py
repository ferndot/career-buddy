"""A number written as a digit or a word is the same number; a bare digit is never a new term."""

from career_buddy.domain.rewording import specifics, verify_rewording


def test_a_digit_matches_the_same_number_written_as_a_word():
    assert specifics("Led two teams of engineers", "Led 2 teams of engineers", []) == []
    assert specifics("Led 2 teams of engineers", "Led two teams of engineers", []) == []


def test_a_bare_digit_is_not_reported_as_a_new_term():
    reasons = specifics("Cut batch time to 90 minutes", "Cut batch time to 90 minutes across 3 pipelines", [])
    assert reasons == ["number not in the source: 3"]


def test_a_number_the_source_does_not_state_is_still_rejected():
    assert "number not in the source: 12" in verify_rewording("Led a team", "Led a team of 12", [])


def test_one_is_not_read_as_a_number():
    assert specifics("Owned the release", "One of the owners of the release", []) == []
