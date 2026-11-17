"""Generating a resume or letter over HTTP, with the LLM mocked at the transport: what the writer is sent, what it may write,
grounding, the one repair call, and the flags and thresholds that follow."""

import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from career_buddy.web.app import create_app
from llm_support import connect_mock
from test_api import seed_jane

RESUME = {"template": "resume-classic"}
LETTER = {"template": "cover-letter", "inputs": {"company": "Acme", "role": "Engineer"}}
CUT = "Cut build times by 60%"
MIGRATED = "Migrated 40 services to Kubernetes"
ETL = "Built ETL jobs"


class Model:
    """A mocked model. `write` and `repair` get the payload the writer sent and return the JSON object it answers with.
    `repair=None` makes the repair call fail with a server error."""

    def __init__(self, write=lambda p: {}, repair=None, status: int = 200) -> None:
        self.write, self.repair, self.status = write, repair, status
        self.payloads: list[dict] = []
        self.systems: list[str] = []  # the system prompt of each call

    def respond(self, request: httpx.Request) -> httpx.Response:
        if self.status != 200:
            return httpx.Response(self.status, text="no")
        messages = json.loads(request.content)["messages"]
        payload = json.loads(messages[-1]["content"])
        self.payloads.append(payload)
        self.systems.append(messages[0]["content"])
        answer = self.repair if "failed" in payload else self.write
        if answer is None:
            return httpx.Response(500, text="no")
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(answer(payload))}}]})


def find(payload: dict, text: str, kind: str | None = None) -> str:
    return next(f["id"] for f in payload["facts"] if text in f["text"] and kind in (None, f["kind"]))


@pytest.fixture(autouse=True)
def no_env_llm(monkeypatch) -> None:
    monkeypatch.delenv("CAREER_BUDDY_LLM_BASE_URL", raising=False)


def open_client(tmp_path: Path, model: Model | None = None) -> TestClient:
    client = TestClient(create_app(tmp_path, llm_transport=httpx.MockTransport(model.respond) if model else None))
    client.__enter__()
    seed_jane(client)  # before the model connects, so the offline reader finishes the import in the call
    if model:
        connect_mock(client)
    return client


@pytest.fixture
def client(tmp_path: Path):
    c = open_client(tmp_path)
    yield c
    c.__exit__(None, None, None)


def generate(client: TestClient, body: dict, status: int = 200) -> dict:
    res = client.post("/api/documents/generate", json=body)
    assert res.status_code == status, res.text
    return res.json()


def ids(client: TestClient) -> dict[str, str]:
    """Jane's facts by text: the achievements, skills and positions."""
    profile = client.get("/api/profile").json()
    found = {a: i for p in profile["positions"] for a, i in zip(p["achievements"], p["achievement_ids"])}
    return found | dict(zip(profile["skills"], profile["skill_ids"])) | {p["title"]: p["id"] for p in profile["positions"]}


def hide(client: TestClient, fact_id: str) -> None:
    fact = next(f for f in client.get("/api/facts").json() if f["id"] == fact_id)
    assert client.patch(f"/api/facts/{fact_id}", json={"attributes": {**fact["attributes"], "hidden": "true"}}).status_code == 200


# a resume of Jane's: a summary, three bullets, two skills. Four written slots, so one rejected slot is 25%.
def good(p: dict) -> dict:
    cut, kube, etl = find(p, CUT), find(p, MIGRATED), find(p, ETL)
    return {"summary": {"text": "Platform engineer who cut build times by 60%.", "fact_ids": [find(p, "Senior Engineer", "position"), cut]},
            "bullets": [{"fact_id": cut, "text": "Reduced build times by 60%"}, {"fact_id": kube, "text": "Moved 40 services to Kubernetes"},
                        {"fact_id": etl, "text": "Built ETL jobs"}],
            "skill_ids": [find(p, "Kubernetes", "skill"), find(p, "Python", "skill")]}


# --- without a model ---

def test_without_a_model_generate_is_503_with_a_stable_code(client: TestClient) -> None:
    for body in (RESUME, LETTER, {**RESUME, "instructions": "x" * 2000}):
        res = client.post("/api/documents/generate", json=body)
        assert res.status_code == 503 and res.json()["code"] == "llm_unavailable" and "Settings" in res.json()["detail"]


def test_the_directions_are_free_text_up_to_2000_characters(client: TestClient) -> None:
    assert client.post("/api/documents/generate", json={**RESUME, "instructions": "x" * 2001}).status_code == 422


def test_unknown_template_is_404_and_a_letter_without_company_and_role_is_422_even_without_a_model(client: TestClient) -> None:
    generate(client, {"template": "nope"}, 404)
    generate(client, {"template": "cover-letter"}, 422)


def test_a_model_that_is_down_is_503_with_the_same_code(tmp_path: Path) -> None:
    with open_client(tmp_path, Model(status=500)) as client:
        res = client.post("/api/documents/generate", json=RESUME)
    assert res.status_code == 503 and res.json()["code"] == "llm_unavailable" and "500" in res.json()["detail"]


# --- what the writer is sent ---

def test_the_writer_is_sent_every_printed_fact_with_its_dates_and_no_name_or_contact_details(tmp_path: Path) -> None:
    model = Model(good)
    with open_client(tmp_path, model) as client:
        generate(client, {**RESUME, "job_text": "Python platform engineer, Kubernetes", "instructions": "Warm, and stress Kubernetes",
                          "inputs": {"company": "Acme", "role": "Platform Engineer"}})
        known = ids(client)
    assert len(model.payloads) == 1
    sent = model.payloads[0]
    assert sent["kind"] == "resume" and sent["directions"] == "Warm, and stress Kubernetes" and sent["posting"] == "Python platform engineer, Kubernetes"
    assert sent["company"] == "Acme" and sent["role"] == "Platform Engineer" and sent["caps"] == {"pages": 1, "bullets_per_position": 3, "skills": 10}
    by_text = {f["text"].split("\n")[0]: f for f in sent["facts"]}
    assert {f["kind"] for f in sent["facts"]} == {"summary", "position", "achievement", "skill", "education"}
    assert {CUT, MIGRATED, ETL, "Python", "Kubernetes", "Senior Engineer at Acme Corp", "Engineer at Globex", "Builds reliable data pipelines",
            "BSc Computer Science, University of Lisbon"} == set(by_text)
    cut, senior = by_text[CUT], by_text["Senior Engineer at Acme Corp"]
    assert cut["id"] == known[CUT] and cut["position_id"] == senior["id"] == known["Senior Engineer"]
    assert "2019" in senior["started"] and "2023" in senior["finished"]  # the position's period goes with the position and its achievements
    assert (cut["started"], cut["finished"]) == (senior["started"], senior["finished"])
    assert "2016" in by_text["Engineer at Globex"]["started"] and "2019" in by_text["Engineer at Globex"]["finished"]
    edu = by_text["BSc Computer Science, University of Lisbon"]
    assert (edu["started"], edu["finished"]) == ("2012", "2016")
    assert by_text["Python"]["started"] == ""
    text = json.dumps(sent)
    assert "Jane" not in text and "Portugal" not in text and "Platform engineer" not in text  # no name, location or headline


def test_every_visible_fact_is_sent_even_when_a_position_has_many(tmp_path: Path) -> None:
    model = Model(good)
    with open_client(tmp_path, model) as client:
        senior = ids(client)["Senior Engineer"]
        extra = [client.post("/api/facts", json={"kind": "Achievement", "title": f"Extra task {n}", "parent_id": senior}).json()["id"] for n in range(8)]
        generate(client, RESUME)
    assert set(extra) <= {f["id"] for f in model.payloads[0]["facts"]}  # a position with eleven achievements: all eleven are in the request


def test_a_hidden_fact_is_not_sent_and_cannot_be_printed(tmp_path: Path) -> None:
    model = Model()
    with open_client(tmp_path, model) as client:
        known = ids(client)
        hide(client, known[ETL])
        hide(client, known["Kubernetes"])

        def names_them(p):  # the model writes bullets and skills for facts it was not sent
            return {"bullets": [{"fact_id": known[ETL], "text": "Built ETL"}, {"fact_id": known[CUT], "text": "Reduced build times by 60%"}],
                    "skill_ids": [known["Kubernetes"], known["Python"]], "summary": {"text": "Engineer.", "fact_ids": [known[CUT]]}}

        model.write = names_them
        draft = generate(client, RESUME)
    sent = model.payloads[0]["facts"]
    texts = {f["text"].split("\n")[0] for f in sent}
    assert {CUT, MIGRATED, "Python"} <= texts and not texts & {ETL, "Kubernetes"}
    assert not {known[ETL], known["Kubernetes"]} & {f["id"] for f in sent}
    assert set(draft["slots"]) == {"summary", f"bullet:{known[CUT]}", "skills"}
    assert draft["slots"]["skills"] == "Python" and draft["flags"] == {}  # dropped, not flagged


def test_the_posting_is_cut_to_6000_characters_and_pinned_slots_are_left_to_the_user(tmp_path: Path) -> None:
    model = Model(good)
    with open_client(tmp_path, model) as client:
        known = ids(client)
        pinned = ["summary", f"bullet:{known[ETL]}"]
        draft = generate(client, {**RESUME, "job_text": "p" * 7000, "pinned": pinned})
    assert len(model.payloads[0]["posting"]) == 6000 and model.payloads[0]["pinned"] == sorted(pinned)
    assert "summary" not in draft["slots"] and f"bullet:{known[ETL]}" not in draft["slots"]  # the model wrote them; they are the user's


# --- what comes back ---

def test_the_returned_slots_come_from_the_model_and_cite_their_facts(tmp_path: Path) -> None:
    with open_client(tmp_path, Model(good)) as client:
        known = ids(client)
        draft = generate(client, RESUME)
    assert draft["flags"] == {}
    assert draft["slots"] == {"summary": "Platform engineer who cut build times by 60%.", f"bullet:{known[CUT]}": "Reduced build times by 60%",
                              f"bullet:{known[MIGRATED]}": "Moved 40 services to Kubernetes", f"bullet:{known[ETL]}": "Built ETL jobs",
                              "skills": "Kubernetes, Python"}
    assert draft["cites"]["summary"] == [known["Senior Engineer"], known[CUT]] and draft["cites"]["skills"] == [known["Kubernetes"], known["Python"]]


def test_the_resume_length_of_the_request_sets_the_caps_and_is_one_page_when_left_out(tmp_path: Path) -> None:
    model = Model(good)
    with open_client(tmp_path, model) as client:
        for pages in (2, 3):
            generate(client, {**RESUME, "resume_pages": pages})
        assert client.post("/api/documents/generate", json={**RESUME, "resume_pages": 4}).status_code == 422
    assert [m["caps"] for m in model.payloads] == [{"pages": 2, "bullets_per_position": 5, "skills": 15},
                                                  {"pages": 3, "bullets_per_position": 7, "skills": 20}]


def test_a_letter_is_the_models_paragraphs_with_the_company_and_role_named(tmp_path: Path) -> None:
    def write(p):
        senior, cut = find(p, "Senior Engineer", "position"), find(p, CUT)
        return {"paragraphs": [
            {"text": "I am applying for the Engineer role at Acme because platform reliability is the work I enjoy most.", "fact_ids": [senior]},
            {"text": "As Senior Engineer I cut build times by 60%, which gave every team faster feedback.", "fact_ids": [senior, cut]},
            {"text": "I would welcome a conversation about the role.", "fact_ids": [senior]}]}

    model = Model(write)
    with open_client(tmp_path, model) as client:
        draft = generate(client, LETTER)
    assert model.payloads[0]["kind"] == "letter" and "caps" not in model.payloads[0] and model.payloads[0]["company"] == "Acme"
    assert list(draft["slots"]) == ["para:1", "para:2", "para:3"] and draft["flags"] == {}
    assert draft["slots"]["para:2"].startswith("As Senior Engineer I cut build times by 60%") and len(draft["cites"]["para:2"]) == 2


# --- grounding, the repair and the thresholds ---

def test_an_invented_number_is_rejected_and_the_one_repair_call_covers_only_that_slot_and_its_reasons(tmp_path: Path) -> None:
    def write(p):
        out = good(p)
        out["bullets"][0]["text"] = "Reduced build times by 90%"
        return out

    def repair(p):
        return {"slots": [{"slot": s["slot"], "text": "Reduced build times by 60%", "fact_ids": s["fact_ids"]} for s in p["failed"]]}

    model = Model(write, repair)
    with open_client(tmp_path, model) as client:
        known = ids(client)
        draft = generate(client, RESUME)
    assert len(model.payloads) == 2  # one writing call and one repair call
    failed = model.payloads[1]["failed"]
    assert [f["slot"] for f in failed] == [f"bullet:{known[CUT]}"] and failed[0]["text"] == "Reduced build times by 90%"
    assert "number not in the source: 90" in failed[0]["reasons"][0]
    assert [f["id"] for f in model.payloads[1]["facts"]] == [known[CUT]]  # only the facts the failed slot cites
    assert draft["slots"][f"bullet:{known[CUT]}"] == "Reduced build times by 60%" and draft["flags"] == {}


def test_the_prompt_is_the_versioned_file_for_the_kind_and_the_repair_call_adds_the_repair_rules(tmp_path: Path) -> None:
    model = Model(lambda p: {**good(p), "bullets": [{**good(p)["bullets"][0], "text": "Reduced build times by 90%"}, *good(p)["bullets"][1:]]},
                  lambda p: {"slots": []})
    letter = Model(lambda p: {})
    with open_client(tmp_path, model) as client:
        generate(client, RESUME)
    write, repair = model.systems
    assert write.startswith("You write text for a person's job application") and "Write the text of a resume." in write
    assert "Write the body of a cover letter" not in write and "were rejected for the reasons given" not in write
    assert "were rejected for the reasons given" in repair and "Write the text of a resume." in repair
    with open_client(tmp_path / "letter", letter) as client:
        client.post("/api/documents/generate", json=LETTER)
    assert "Write the body of a cover letter" in letter.systems[0] and "Write the text of a resume." not in letter.systems[0]


def test_a_second_failure_is_final_a_bullet_shows_the_facts_own_title_flagged_and_the_rest_is_kept(tmp_path: Path) -> None:
    def write(p):
        out = good(p)
        out["bullets"][0]["text"] = "Reduced build times by 90%"
        return out

    model = Model(write, lambda p: {"slots": [{"slot": s["slot"], "text": "Reduced build times by 80%", "fact_ids": s["fact_ids"]} for s in p["failed"]]})
    with open_client(tmp_path, model) as client:
        known = ids(client)
        draft = generate(client, RESUME)
    assert len(model.payloads) == 2  # the repair runs exactly once
    slot = f"bullet:{known[CUT]}"
    assert draft["slots"][slot] == CUT and draft["flags"][slot]["code"] == "not_rewritten" and "80" in draft["flags"][slot]["reasons"][0]
    assert draft["slots"][f"bullet:{known[ETL]}"] == "Built ETL jobs" and set(draft["flags"]) == {slot} and "summary" in draft["slots"]


def test_a_summary_that_fails_twice_is_left_empty_and_flagged_with_the_reason(tmp_path: Path) -> None:
    def write(p):
        out = good(p)
        out["summary"]["text"] = "Platform engineer with 12 years at Initech."
        return out

    model = Model(write, lambda p: {"slots": []})  # the repair answers nothing
    with open_client(tmp_path, model) as client:
        draft = generate(client, RESUME)
    assert len(model.payloads) == 2
    assert draft["slots"]["summary"] == "" and draft["flags"]["summary"]["code"] == "rejected"
    assert any(r.startswith("number not in the source: 12") for r in draft["flags"]["summary"]["reasons"])
    assert any("Initech" in r for r in draft["flags"]["summary"]["reasons"])  # an employer the facts lack


def test_a_repair_call_that_fails_leaves_the_slot_flagged_not_a_503(tmp_path: Path) -> None:
    def write(p):
        out = good(p)
        out["bullets"][1]["text"] = "Moved 40 services to Terraform"
        return out

    with open_client(tmp_path, Model(write, repair=None)) as client:
        known = ids(client)
        draft = generate(client, RESUME)
    assert draft["flags"][f"bullet:{known[MIGRATED]}"]["code"] == "not_rewritten" and draft["slots"][f"bullet:{known[MIGRATED]}"] == MIGRATED


def test_an_unknown_id_is_dropped_and_a_slot_citing_no_printed_fact_is_repaired_with_all_the_facts(tmp_path: Path) -> None:
    def write(p):
        out = good(p)
        out["bullets"].append({"fact_id": "not-a-fact", "text": "Led a team of twelve"})  # dropped: there is nothing to repair
        out["summary"] = {"text": "Platform engineer.", "fact_ids": ["ghost"]}  # no cited fact is left
        return out

    model = Model(write, lambda p: {"slots": [{"slot": "summary", "text": "Platform engineer.", "fact_ids": [find(p, CUT)]}]})
    with open_client(tmp_path, model) as client:
        draft = generate(client, RESUME)
    assert model.payloads[1]["failed"][0]["reasons"] == ["cites no fact"] and len(model.payloads[1]["facts"]) == 9  # none cited: all
    assert draft["slots"]["summary"] == "Platform engineer." and draft["flags"] == {} and "not-a-fact" not in json.dumps(draft)


def test_more_than_30_percent_of_the_slots_rejected_after_the_repair_is_a_502(tmp_path: Path) -> None:
    def write(p):
        out = good(p)
        out["bullets"][0]["text"] = "Reduced build times by 90%"
        out["bullets"][1]["text"] = "Moved 70 services to Kubernetes"  # two of four written slots
        return out

    model = Model(write, lambda p: {"slots": []})
    with open_client(tmp_path, model) as client:
        res = client.post("/api/documents/generate", json=RESUME)
    assert res.status_code == 502 and res.json()["code"] == "ungrounded" and len(model.payloads) == 2
    assert len(res.json()["rejected"]) == 2 and "unchanged" in res.json()["detail"]


def test_a_reply_with_nothing_kept_is_a_502(tmp_path: Path) -> None:
    with open_client(tmp_path, Model(lambda p: {})) as client:
        assert client.post("/api/documents/generate", json=RESUME).status_code == 502
