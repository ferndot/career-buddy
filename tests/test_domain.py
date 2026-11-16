"""Unit tests for the pure parts: text splitting, ranking, and the heuristic extractor."""

import asyncio

from career_buddy.adapters.inference.heuristic import HeuristicExtractor
from career_buddy.domain.model import FactKind
from career_buddy.domain.profile import PositionView, Profile, assemble_profile, rank_for_job
from career_buddy.domain.text import split_bullets


def test_split_bullets_separates_prose_from_bullets() -> None:
    bullets, prose = split_bullets("Led a team.\n- Shipped v2\n• Hired 3")
    assert bullets == ("Shipped v2", "Hired 3")
    assert prose == "Led a team."


def test_rank_prefers_positions_matching_the_job() -> None:
    profile = Profile(
        name="X",
        positions=(
            PositionView("Designer", "A", achievements=("Drew logos",)),
            PositionView("Data Engineer", "B", achievements=("Built Spark pipelines",), skills=("Spark",)),
        ),
        skills=("Spark", "Painting"),
    )
    positions, skills = rank_for_job(profile, "Looking for a data engineer who knows Spark")
    assert positions[0].title == "Data Engineer"
    assert skills == ["Spark"]


def test_heuristic_extracts_positions_bullets_and_skills() -> None:
    text = "Grace Hopper\n\nExperience\nCompiler Lead at Remington, 1950 - 1959\n- Built the A-0 compiler\n\nSkills\nCOBOL, Fortran\n"
    batch = asyncio.run(HeuristicExtractor().extract(text, "t"))
    profile = assemble_profile(batch)
    assert profile.name == "Grace Hopper"
    assert profile.positions[0].title == "Compiler Lead"
    assert profile.positions[0].organization == "Remington"
    assert profile.positions[0].achievements == ("Built the A-0 compiler",)
    assert profile.skills == ("COBOL", "Fortran")
    assert any(f.kind == FactKind.POSITION for f in batch.facts)


def test_redstring_adapter_maps_model_json_to_a_profile() -> None:
    import httpx
    import json

    from career_buddy.adapters.inference.redstring_extractor import RedstringExtractor
    from career_buddy.adapters.inference.structured_openai import StructuredOpenAIProvider

    reply = {
        "entities": [
            {"name": "Alan Turing", "entity_type": "Person"},
            {"name": "Lecturer", "entity_type": "Position"},
            {"name": "Manchester", "entity_type": "Organization"},
            {"name": "Designed the Turing machine model", "entity_type": "Achievement"},
            {"name": "Cryptanalysis", "entity_type": "Skill"},
        ],
        "relationships": [
            {"source_name": "Alan Turing", "target_name": "Lecturer", "relationship_type": "HAS_POSITION"},
            {"source_name": "Lecturer", "target_name": "Manchester", "relationship_type": "AT"},
            {"source_name": "Lecturer", "target_name": "Designed the Turing machine model", "relationship_type": "ACHIEVED"},
            {"source_name": "Alan Turing", "target_name": "Cryptanalysis", "relationship_type": "HAS_SKILL"},
        ],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(reply)}}]})

    client = httpx.AsyncClient(base_url="http://model.test/v1/", transport=httpx.MockTransport(handler))
    extractor = RedstringExtractor(StructuredOpenAIProvider(client, "m"))
    profile = assemble_profile(asyncio.run(extractor.extract("text", "t")))
    assert profile.name == "Alan Turing"
    assert profile.positions[0].achievements == ("Designed the Turing machine model",)
    assert profile.skills == ("Cryptanalysis",)
