"""A saved document is live: it keeps its layout, the user's overrides, the writer's generated text and what it was built from
(the settings). Everything else is found from the facts at every download."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from test_generate_api import CUT, ETL, LETTER, MIGRATED, RESUME, Model, experience, find, good, ids, letter_answer, open_client, section

OLD = "Reduced build times by 60%"
NEW = "Lowered build times by 60%"


def save(client: TestClient, body: dict = RESUME, **extra) -> dict:
    res = client.post("/api/saved-documents", json={**body, **extra})
    assert res.status_code == 201, res.text
    return res.json()


def stored(tmp_path: Path, record: dict, name: str) -> Path:
    return tmp_path / "objects" / "documents" / record["id"] / name


def txt(client: TestClient, record: dict) -> str:
    return client.get(f"/api/saved-documents/{record['id']}/file", params={"format": "txt"}).text


def content(client: TestClient, record: dict) -> dict:
    return client.get(f"/api/saved-documents/{record['id']}/content").json()


def written(client: TestClient, summary: str | None = None, **bullets: str) -> list[dict]:
    """The sections a client sends with a save: an optional summary and one bullet for each fact id (`b<fact id>=text`; "" leaves the fact's own words)."""
    profile = client.get("/api/profile").json()
    out = [section("summary", {"text": summary, "fact_ids": []})] if summary is not None else []
    items = [{"position_id": p["id"], "bullets": [{"text": bullets[a], "fact_ids": [a]} for a in p["achievement_ids"] if a in bullets]} for p in profile["positions"]]
    return [*out, {"key": "experience", "items": [i for i in items if i["bullets"]]}] if any(i["bullets"] for i in items) else out


def patch(client: TestClient, fact_id: str, title: str) -> None:
    assert client.patch(f"/api/facts/{fact_id}", json={"title": title}).status_code == 200


def test_a_save_keeps_the_settings_and_none_of_the_text(tmp_path: Path) -> None:
    with open_client(tmp_path) as client:
        record = save(client, job_text="Python platform",
                      inputs={"company": "Acme"}, instructions="  Warm  ", font="serif", paper="a4")
        assert content(client, record)["source"] == {"template": "resume-classic", "job_text": "Python platform", "inputs": {"company": "Acme"},
                                                     "instructions": "Warm", "resume_pages": "default", "template_instructions": "", "job_url": ""}
        raw = stored(tmp_path, record, "source.json").read_text()
        assert "Jane" not in raw and CUT not in raw
        assert json.loads(stored(tmp_path, record, "meta.json").read_text())["paper"] == "a4"
        out = txt(client, record)
    assert all(text in out for text in (CUT, MIGRATED, "Python", "Kubernetes", "University of Lisbon"))  # every visible fact prints


def test_the_writers_text_is_kept_apart_from_the_users_overrides_and_is_not_in_the_layout(tmp_path: Path) -> None:
    with open_client(tmp_path) as client:
        known = ids(client)
        record = save(client, sections=written(client, "Platform engineer who ships.", **{known[CUT]: OLD, known[ETL]: ""}),
                      overrides={f"bullet:{known[ETL]}": "Wrote the ETL jobs myself", "bullet:stray": "x"})
        assert json.loads(stored(tmp_path, record, "overrides.json").read_text()) == {f"bullet:{known[ETL]}": "Wrote the ETL jobs myself"}
        assert json.loads(stored(tmp_path, record, "generated.json").read_text()) == {
            "summary": {"text": "Platform engineer who ships.", "source": ""}, f"bullet:{known[CUT]}": {"text": OLD, "source": CUT}}
        html = stored(tmp_path, record, "document.html").read_text()
        assert "Platform engineer who ships" not in html and OLD not in html and "Wrote the ETL" not in html
        c = content(client, record)
        assert c["generated"] == {"summary": "Platform engineer who ships.", f"bullet:{known[CUT]}": OLD}
        assert c["slots"]["summary"] == "Platform engineer who ships." and c["slots"][f"bullet:{known[ETL]}"] == "Wrote the ETL jobs myself"
        out = txt(client, record)
    assert "Platform engineer who ships." in out and f"- {OLD}" in out and "- Wrote the ETL jobs myself" in out and "Builds reliable" not in out


def test_a_summary_written_for_a_person_with_none_gets_a_slot_in_the_layout(tmp_path: Path) -> None:
    with open_client(tmp_path) as client:
        person = client.get("/api/profile").json()["id"]
        assert client.patch(f"/api/facts/{person}", json={"attributes": {"headline": "Platform engineer"}}).status_code == 200  # no summary now
        assert "Summary" not in txt(client, save(client))
        record = save(client, sections=written(client, "Platform engineer who ships."))
        assert 'data-slot="summary"' in stored(tmp_path, record, "document.html").read_text()
        assert "Platform engineer who ships." in txt(client, record)


def test_editing_a_fact_after_saving_changes_the_download_and_an_overridden_slot_does_not_change(tmp_path: Path) -> None:
    with open_client(tmp_path) as client:
        known = ids(client)
        person = client.get("/api/profile").json()["id"]
        record = save(client, overrides={"name": "J. Doe"}, sections=written(client, "Platform engineer who ships.", **{known[CUT]: OLD, known[MIGRATED]: ""}))
        before = txt(client, record)
        assert before.startswith("J. Doe\n") and f"- {OLD}" in before and f"- {MIGRATED}" in before
        patch(client, known[MIGRATED], "Migrated 40 services to Kubernetes in a year")  # a slot with no generated text
        patch(client, person, "Jane Q. Doe")  # a slot with an override
        patch(client, known[CUT], "Cut build times by 70%")  # a slot whose generated text was written from the old words
        after = txt(client, record)
    assert "- Migrated 40 services to Kubernetes in a year" in after and MIGRATED + "\n" not in after
    assert after.startswith("J. Doe\n") and "Jane Q. Doe" not in after  # the user's own words win over the fact
    assert "- Cut build times by 70%" in after and OLD not in after  # stale generated text gives way to the fact
    assert "Platform engineer who ships." in after  # a summary rests on many facts: it stays
    assert content(client, record)["generated"][f"bullet:{known[CUT]}"] == OLD  # not discarded: it shows again if the fact is put back


def reword(p: dict) -> dict:
    return {"sections": [section("summary", {"text": "Engineer who ships reliable systems.", "fact_ids": [find(p, CUT)]}),
                         experience(p, (find(p, CUT), NEW), (find(p, MIGRATED), "Moved 40 services to Kubernetes"), (find(p, ETL), "Built ETL jobs"))]}


def test_regenerating_replaces_generated_text_only_where_there_is_no_override(tmp_path: Path) -> None:
    model = Model(reword)
    with open_client(tmp_path, model) as client:
        known = ids(client)
        record = save(client, overrides={"summary": "My own summary"}, sections=written(client, "Old summary", **{known[CUT]: OLD}), instructions="Warm")
        mine = stored(tmp_path, record, "overrides.json").read_text()
        res = client.post(f"/api/saved-documents/{record['id']}/regenerate", json={})
        assert res.status_code == 200, res.text
        assert model.payloads[0]["pinned"] == ["summary"] and model.payloads[0]["directions"] == "Warm"  # the saved directions and the user's slot
        assert "summary" not in res.json()["slots"] and res.json()["slots"][f"bullet:{known[CUT]}"] == NEW
        assert stored(tmp_path, record, "overrides.json").read_text() == mine
        generated = json.loads(stored(tmp_path, record, "generated.json").read_text())
        assert generated[f"bullet:{known[CUT]}"] == {"text": NEW, "source": CUT} and "summary" not in generated  # replaced; the old summary text goes
        out = txt(client, record)
        assert "My own summary" in out and f"- {NEW}" in out and OLD not in out and "Old summary" not in out
        assert client.post(f"/api/saved-documents/{record['id']}/regenerate", json={"instructions": "Brief"}).status_code == 200
        assert model.payloads[1]["directions"] == "Brief" and content(client, record)["source"]["instructions"] == "Brief"


def test_each_resume_keeps_its_own_length_and_regenerating_uses_it_unless_given_a_new_one(tmp_path: Path) -> None:
    model = Model(reword)
    with open_client(tmp_path, model) as client:
        short, long = save(client, resume_pages=1), save(client)
        assert content(client, short)["source"]["resume_pages"] == 1 and content(client, long)["source"]["resume_pages"] == "default"
        for record in (short, long):
            assert client.post(f"/api/saved-documents/{record['id']}/regenerate", json={}).status_code == 200
        assert client.post(f"/api/saved-documents/{short['id']}/regenerate", json={"resume_pages": "default"}).status_code == 200
        assert client.post(f"/api/saved-documents/{short['id']}/regenerate", json={}).status_code == 200  # the new length was kept
        assert client.post(f"/api/saved-documents/{short['id']}/regenerate", json={"resume_pages": 3}).status_code == 422
        assert content(client, short)["source"]["resume_pages"] == "default" and content(client, long)["source"]["resume_pages"] == "default"
    assert ["1 page long" in system for system in model.systems] == [True, False, False, False]


def test_regenerating_a_letter_gives_it_the_models_paragraphs_under_the_header_and_nothing_else(tmp_path: Path) -> None:
    def write(p):
        senior = find(p, "Senior Engineer", "position")
        return letter_answer(("I am applying for the Engineer role at Acme because reliability is the work I enjoy.", [senior]),
                             ("I would welcome a conversation about the role.", [senior]))

    with open_client(tmp_path, Model(write)) as client:
        record = save(client, LETTER)
        assert txt(client, record).split() == ["Jane", "Doe", "Lisbon,", "Portugal"]  # no code writes a letter: only the header until a writer is asked
        assert client.post(f"/api/saved-documents/{record['id']}/regenerate", json={}).status_code == 200
        lines = [line for line in txt(client, record).splitlines() if line]
    assert lines[:2] == ["Jane Doe", "Lisbon, Portugal"] and len(lines) == 4
    assert lines[2].startswith("I am applying for the Engineer role at Acme") and lines[3] == "I would welcome a conversation about the role."


def test_regenerating_without_a_model_or_a_source_or_a_good_answer_changes_nothing(tmp_path: Path) -> None:
    with open_client(tmp_path) as client:
        record = save(client, sections=written(client, "Kept"))
        res = client.post(f"/api/saved-documents/{record['id']}/regenerate", json={})
        assert res.status_code == 503 and res.json()["code"] == "llm_unavailable"
    with open_client(tmp_path / "other", Model(lambda p: {"sections": []})) as client:
        record = save(client, sections=written(client, "Kept"))
        res = client.post(f"/api/saved-documents/{record['id']}/regenerate", json={})
        assert res.status_code == 502 and res.json()["code"] == "ungrounded" and "Kept" in txt(client, record)  # the last text stays
        stored(tmp_path / "other", record, "source.json").unlink()  # saved before sources were kept
        assert client.post(f"/api/saved-documents/{record['id']}/regenerate", json={}).status_code == 409
        assert client.post("/api/saved-documents/" + "0" * 32 + "/regenerate", json={}).status_code == 404


def test_a_saved_letter_is_one_body_block_whose_paragraphs_are_keyed_by_their_index_and_edits_survive_a_regenerate(tmp_path: Path) -> None:
    def write(p):
        senior = find(p, "Senior Engineer", "position")
        return letter_answer(("I am applying for the Engineer role at Acme because reliability is the work I enjoy.", [senior]),
                             ("I would welcome a conversation about the role.", [senior]))

    with open_client(tmp_path, Model(write)) as client:
        body = section("body", {"text": "First draft one.", "fact_ids": []}, {"text": "First draft two.", "fact_ids": []})
        record = save(client, LETTER, sections=[body], overrides={"para:2": "My closing."})
        assert json.loads(stored(tmp_path, record, "generated.json").read_text()) == {"para:1": {"text": "First draft one.", "source": ""}, "para:2": {"text": "First draft two.", "source": ""}}
        assert "My closing." in txt(client, record) and "First draft two." not in txt(client, record)
        assert client.post(f"/api/saved-documents/{record['id']}/regenerate", json={}).status_code == 200
        lines = [line for line in txt(client, record).splitlines() if line]
    assert lines[2].startswith("I am applying for the Engineer role") and lines[3] == "My closing." and len(lines) == 4  # paragraph 2 is the person's: pinned by its index


def test_a_regenerated_bullet_the_person_edited_keeps_their_words_even_if_the_writer_drops_it(tmp_path: Path) -> None:
    def write(p):
        return {"sections": [section("summary", {"text": "Engineer who ships.", "fact_ids": [find(p, CUT)]}), experience(p, (find(p, MIGRATED), "Moved 40 services to Kubernetes"))]}

    with open_client(tmp_path, Model(write)) as client:
        known = ids(client)
        record = save(client, sections=written(client, "Old.", **{known[CUT]: OLD, known[MIGRATED]: "x"}), overrides={f"bullet:{known[CUT]}": "My cut bullet"})
        assert client.post(f"/api/saved-documents/{record['id']}/regenerate", json={}).status_code == 200
        out = txt(client, record)
    assert "- My cut bullet" in out and "- Moved 40 services to Kubernetes" in out  # the writer left the cut bullet out; the person's is put back in its position
