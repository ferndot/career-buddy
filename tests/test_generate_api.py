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
LETTER = {"template": "cover-letter", "job_text": "Engineer at Acme: Kubernetes platform work", "inputs": {"company": "Acme", "role": "Engineer"}}
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
        payload["facts"] = flat(payload["facts"])
        self.payloads.append(payload)
        self.systems.append(messages[0]["content"])
        answer = self.repair if "failed" in payload else self.write
        if answer is None:
            return httpx.Response(500, text="no")
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(answer(payload))}}]})


def flat(facts: dict) -> list[dict]:
    """The grouped facts of a request as one list of facts with their kind and position, for the fake model to look things up."""
    def one(kind: str, f: dict, pid: str = "", when: dict | None = None) -> dict:
        return {"id": f["id"], "kind": kind, "text": f.get("text") or f.get("title", ""), "position_id": pid, "started": "", "finished": "", **(when or f)} | {"id": f["id"]}
    return [*([one("summary", facts["summary"])] if "summary" in facts else []),
            *(x for p in facts["positions"] for x in [one("position", p), *(one("achievement", a, p["id"], p) for a in p["achievements"])] if "title" in p or x["kind"] == "achievement"),
            *(one("skill", f) for f in facts["skills"]), *(one("education", f) for f in facts["education"])]


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


def section(key: str, *items: dict) -> dict:
    return {"key": key, "items": list(items)}


def experience(p: dict, *written: tuple[str, str]) -> dict:
    """The experience section for (achievement id, text) pairs: each position's bullets together, as the model would write them."""
    position = {f["id"]: f["position_id"] for f in p["facts"]}
    out: dict[str, list] = {}
    for fid, text in written:
        out.setdefault(position[fid], []).append({"text": text, "fact_ids": [fid]})
    return section("experience", *({"position_id": pid, "bullets": bullets} for pid, bullets in out.items()))


def bullets(answer: dict) -> list[dict]:
    return [b for s in answer["sections"] if s["key"] == "experience" for i in s["items"] for b in i["bullets"]]


def items(answer: dict, key: str) -> list[dict]:
    return next(s for s in answer["sections"] if s["key"] == key)["items"]


def nodes(draft: dict, key: str) -> list[dict]:
    """The texts of a section of a draft: its items, or for experience all the bullets."""
    got = next((s for s in draft["sections"] if s["key"] == key), {"items": []})["items"]
    return [b for i in got for b in i["bullets"]] if key == "experience" else got


# a resume of Jane's: a summary, three bullets, a skills line. Four written slots (the skills line is not counted), so one rejected slot is 25%.
def good(p: dict) -> dict:
    cut, kube, etl = find(p, CUT), find(p, MIGRATED), find(p, ETL)
    return {"sections": [
        section("summary", {"text": "Platform engineer who cut build times by 60%.", "fact_ids": [find(p, "Senior Engineer", "position"), cut]}),
        experience(p, (cut, "Reduced build times by 60%"), (kube, "Moved 40 services to Kubernetes"), (etl, "Built ETL jobs")),
        section("skills", {"text": "Kubernetes, Python", "fact_ids": [find(p, "Kubernetes", "skill"), find(p, "Python", "skill")]})]}


def letter_answer(*paragraphs: tuple[str, list[str]]) -> dict:
    return {"sections": [section("body", *({"text": t, "fact_ids": ids_} for t, ids_ in paragraphs))]}


# --- without a model ---

def test_without_a_model_generate_is_503_with_a_stable_code(client: TestClient) -> None:
    for body in (RESUME, LETTER, {**RESUME, "instructions": "x" * 2000}):
        res = client.post("/api/documents/generate", json=body)
        assert res.status_code == 503 and res.json()["code"] == "llm_unavailable" and "Settings" in res.json()["detail"]


def test_the_directions_are_free_text_up_to_2000_characters(client: TestClient) -> None:
    assert client.post("/api/documents/generate", json={**RESUME, "instructions": "x" * 2001}).status_code == 422


def test_unknown_template_is_404_and_a_letter_without_a_posting_or_company_and_role_is_422_even_without_a_model(client: TestClient) -> None:
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
    assert sent["company"] == "Acme" and sent["role"] == "Platform Engineer" and sent["sections"] == ["summary", "experience", "education", "skills"] and "caps" not in sent
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
            return {"sections": [
                section("summary", {"text": "Engineer.", "fact_ids": [known[CUT]]}),
                {"key": "experience", "items": [{"position_id": known["Senior Engineer"], "bullets": [
                    {"text": "Built ETL", "fact_ids": [known[ETL]]}, {"text": "Reduced build times by 60%", "fact_ids": [known[CUT]]}]}]},
                section("skills", {"text": "Kubernetes, Python", "fact_ids": [known["Kubernetes"], known["Python"]]})]}

        model.write = names_them
        draft = generate(client, RESUME)
    sent = model.payloads[0]["facts"]
    texts = {f["text"].split("\n")[0] for f in sent}
    assert {CUT, MIGRATED, "Python"} <= texts and not texts & {ETL, "Kubernetes"}
    assert not {known[ETL], known["Kubernetes"]} & {f["id"] for f in sent}
    assert set(draft["slots"]) == {"summary", f"bullet:{known[CUT]}"}
    assert set(draft["flags"]) == {"skills"} and "skills" not in draft["slots"]  # the line naming a hidden skill is rejected and left empty; it does not sink the draft


def test_the_posting_is_cut_to_6000_characters_and_pinned_slots_are_left_to_the_user(tmp_path: Path) -> None:
    model = Model(good)
    with open_client(tmp_path, model) as client:
        known = ids(client)
        pinned = ["summary", f"bullet:{known[ETL]}"]
        draft = generate(client, {**RESUME, "job_text": "p" * 7000, "pinned": pinned})
    assert len(model.payloads[0]["posting"]) == 6000 and model.payloads[0]["pinned"] == sorted(pinned)
    assert "summary" not in draft["slots"] and f"bullet:{known[ETL]}" not in draft["slots"]  # the model wrote them; they are the user's
    assert nodes(draft, "summary")[0]["slot"] == "summary" and f"bullet:{known[ETL]}" in [b["slot"] for b in nodes(draft, "experience")]  # and keep their place


# --- what comes back ---

def test_the_returned_slots_come_from_the_model_and_cite_their_facts(tmp_path: Path) -> None:
    with open_client(tmp_path, Model(good)) as client:
        known = ids(client)
        draft = generate(client, RESUME)
    assert draft["flags"] == {}
    assert draft["slots"] == {"summary": "Platform engineer who cut build times by 60%.", f"bullet:{known[CUT]}": "Reduced build times by 60%",
                              f"bullet:{known[MIGRATED]}": "Moved 40 services to Kubernetes", f"bullet:{known[ETL]}": "Built ETL jobs",
                              "skills": "Kubernetes, Python"}
    assert nodes(draft, "summary")[0]["fact_ids"] == [known["Senior Engineer"], known[CUT]] and nodes(draft, "skills")[0]["fact_ids"] == [known["Kubernetes"], known["Python"]]
    senior = next(i for i in next(s for s in draft["sections"] if s["key"] == "experience")["items"] if i["position_id"] == known["Senior Engineer"])
    assert senior["heading"].startswith("Senior Engineer, Acme Corp") and [b["fact_ids"] for b in senior["bullets"]][0] == [known[CUT]]  # the heading is the facts' own


def test_the_resume_length_of_the_request_sets_the_caps_and_is_one_page_when_left_out(tmp_path: Path) -> None:
    model = Model(good)
    with open_client(tmp_path, model) as client:
        for pages in (2, 3):
            generate(client, {**RESUME, "resume_pages": pages})
        assert client.post("/api/documents/generate", json={**RESUME, "resume_pages": 4}).status_code == 422
    assert "2 pages long. At most 5 bullets for each position and 15 skills" in model.systems[0]
    assert "3 pages long. At most 7 bullets for each position and 20 skills" in model.systems[1]
    assert all("caps" not in m for m in model.payloads)


def test_a_letter_is_one_body_block_of_the_models_paragraphs_with_the_company_and_role_named(tmp_path: Path) -> None:
    def write(p):
        senior, cut = find(p, "Senior Engineer", "position"), find(p, CUT)
        return letter_answer(("I am applying for the Engineer role at Acme because platform reliability is the work I enjoy most.", [senior]),
                             ("As Senior Engineer I cut build times by 60%, which gave every team faster feedback.", [senior, cut]),
                             ("I would welcome a conversation about the role.", [senior]))

    model = Model(write)
    with open_client(tmp_path, model) as client:
        draft = generate(client, LETTER)
    assert model.payloads[0]["kind"] == "letter" and model.payloads[0]["sections"] == ["body"] and model.payloads[0]["company"] == "Acme"
    assert [s["key"] for s in draft["sections"]] == ["body"]  # one block
    assert list(draft["slots"]) == ["para:1", "para:2", "para:3"] and draft["flags"] == {}
    assert draft["slots"]["para:2"].startswith("As Senior Engineer I cut build times by 60%") and len(nodes(draft, "body")[1]["fact_ids"]) == 2


# --- grounding, the repair and the thresholds ---

def test_an_invented_number_is_rejected_and_the_one_repair_call_covers_only_that_slot_and_its_reasons(tmp_path: Path) -> None:
    def write(p):
        out = good(p)
        bullets(out)[0]["text"] = "Reduced build times by 90%"
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
    def write(p):
        out = good(p)
        bullets(out)[0]["text"] = "Reduced build times by 90%"
        return out

    model = Model(write, lambda p: {"slots": []})
    letter = Model(lambda p: {"sections": []})
    with open_client(tmp_path, model) as client:
        generate(client, RESUME)
    write, repair = model.systems
    assert write.startswith("You write a person's job application document") and "Write the whole resume at once" in write and "Template instructions:" not in write
    assert "Write the body of a cover letter" not in write and "were rejected for the reasons given" not in write
    assert "were rejected for the reasons given" in repair and "Write the whole resume at once" not in repair
    with open_client(tmp_path / "letter", letter) as client:
        client.post("/api/documents/generate", json=LETTER)
    assert "Write the body of a cover letter" in letter.systems[0] and "Write the whole resume at once" not in letter.systems[0]


def test_a_second_failure_is_final_a_bullet_shows_the_facts_own_title_flagged_and_the_rest_is_kept(tmp_path: Path) -> None:
    def write(p):
        out = good(p)
        bullets(out)[0]["text"] = "Reduced build times by 90%"
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
        items(out, "summary")[0]["text"] = "Platform engineer with 12 years at Initech."
        return out

    model = Model(write, lambda p: {"slots": []})  # the repair answers nothing
    with open_client(tmp_path, model) as client:
        draft = generate(client, RESUME)
    assert len(model.payloads) == 2
    assert nodes(draft, "summary")[0]["text"] == "" and "summary" not in draft["slots"] and draft["flags"]["summary"]["code"] == "rejected"
    assert any(r.startswith("number not in the source: 12") for r in draft["flags"]["summary"]["reasons"])
    assert any("Initech" in r for r in draft["flags"]["summary"]["reasons"])  # an employer the facts lack


def test_a_repair_call_that_fails_leaves_the_slot_flagged_not_a_503(tmp_path: Path) -> None:
    def write(p):
        out = good(p)
        bullets(out)[1]["text"] = "Moved 40 services to Terraform"
        return out

    with open_client(tmp_path, Model(write, repair=None)) as client:
        known = ids(client)
        draft = generate(client, RESUME)
    assert draft["flags"][f"bullet:{known[MIGRATED]}"]["code"] == "not_rewritten" and draft["slots"][f"bullet:{known[MIGRATED]}"] == MIGRATED


def test_an_unknown_id_is_dropped_and_a_slot_citing_no_printed_fact_is_repaired_with_all_the_facts(tmp_path: Path) -> None:
    def write(p):
        out = good(p)
        next(s for s in out["sections"] if s["key"] == "experience")["items"][0]["bullets"].append({"text": "Led a team of twelve", "fact_ids": ["not-a-fact"]})  # dropped: there is nothing to repair
        items(out, "summary")[0].update({"text": "Platform engineer.", "fact_ids": ["ghost"]})  # no cited fact is left
        return out

    model = Model(write, lambda p: {"slots": [{"slot": "summary", "text": "Platform engineer.", "fact_ids": [find(p, CUT)]}]})
    with open_client(tmp_path, model) as client:
        draft = generate(client, RESUME)
    assert model.payloads[1]["failed"][0]["reasons"] == ["cites no fact"] and len(model.payloads[1]["facts"]) == 9  # none cited: all
    assert draft["slots"]["summary"] == "Platform engineer." and draft["flags"] == {} and "not-a-fact" not in json.dumps(draft)


def test_more_than_30_percent_of_the_slots_rejected_after_the_repair_is_a_502(tmp_path: Path) -> None:
    def write(p):
        out = good(p)
        bullets(out)[0]["text"] = "Reduced build times by 90%"
        bullets(out)[1]["text"] = "Moved 70 services to Kubernetes"  # two of four written slots
        return out

    model = Model(write, lambda p: {"slots": []})
    with open_client(tmp_path, model) as client:
        res = client.post("/api/documents/generate", json=RESUME)
    assert res.status_code == 502 and res.json()["code"] == "ungrounded" and len(model.payloads) == 2
    assert len(res.json()["rejected"]) == 2 and "unchanged" in res.json()["detail"]


def test_a_reply_with_nothing_kept_is_a_502(tmp_path: Path) -> None:
    with open_client(tmp_path, Model(lambda p: {"sections": []})) as client:
        assert client.post("/api/documents/generate", json=RESUME).status_code == 502


def test_an_answer_that_is_not_a_document_is_503_like_any_unreadable_answer(tmp_path: Path) -> None:
    for answer in ({}, {"sections": "none"}, {"sections": [{"items": []}]}):
        with open_client(tmp_path / str(len(str(answer))), Model(lambda p, a=answer: a)) as client:
            res = client.post("/api/documents/generate", json=RESUME)
        assert res.status_code == 503 and res.json()["code"] == "llm_unavailable"


def test_a_cover_letter_needs_no_inputs_when_a_posting_is_given_and_the_review_supplies_the_company_and_role(tmp_path: Path) -> None:
    def write(p):
        senior = find(p, "Senior Engineer", "position")
        return letter_answer(("I am applying for the Platform Engineer role at Initech to keep building reliable platforms.", [senior]))

    model = Model(write)
    posting = "Initech is hiring a Platform Engineer to run Kubernetes."
    with open_client(tmp_path, model) as client:
        draft = generate(client, {"template": "cover-letter", "job_text": posting, "inputs": {"company": "Initech", "role": "Platform Engineer"}})
        generate(client, {"template": "cover-letter"}, 422)  # no posting and no company and role: nothing to write it for
    assert model.payloads[0]["posting"] == posting and model.payloads[0]["company"] == "Initech" and model.payloads[0]["role"] == "Platform Engineer"
    assert draft["flags"] == {} and "Initech" in draft["slots"]["para:1"]  # the company in the posting is not an invented name
    assert "not an email" in model.systems[0] and "no subject line" in model.systems[0]
    assert "Template instructions" not in model.systems[0]  # nothing is added unless the request carries it


def test_template_instructions_go_to_the_writer_and_are_kept_for_regenerating(tmp_path: Path) -> None:
    def write(p):
        return letter_answer(("I would like to build platforms at Acme.", [find(p, "Senior Engineer", "position")]))

    model = Model(write)
    style = "Direct and concise: three short paragraphs."
    with open_client(tmp_path, model) as client:
        generate(client, {**LETTER, "template_instructions": style})
        saved = client.post("/api/saved-documents", json={**LETTER, "template_instructions": style, "sections": [section("body", {"text": "I would like to build platforms at Acme.", "fact_ids": []})]})
        assert saved.status_code == 201
        client.post(f"/api/saved-documents/{saved.json()['id']}/regenerate", json={})
    assert len(model.systems) == 2 and all(f"Template instructions: {style}" in system for system in model.systems)  # the template's words go in the system message
