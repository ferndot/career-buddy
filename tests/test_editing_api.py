"""Blackbox tests through HTTP: edit, hide, add by hand, and confirm or undo a duplicate merge."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from career_graph.web.app import create_app
from test_api import linkedin_zip

PDF_TEXT = b"Jane Doe\n\nExperience\nPlatform Lead at Acme, 2020 - 2021\n- Ran the platform team\n"


def import_linkedin(client: TestClient) -> None:
    client.post("/api/import/linkedin", files={"file": ("export.zip", linkedin_zip(), "application/zip")})


def import_resume_file(client: TestClient) -> None:
    client.post("/api/import/file", files={"file": ("resume.txt", PDF_TEXT, "text/plain")})


def position(client: TestClient, title: str) -> dict:
    return next(p for p in client.get("/api/profile").json()["positions"] if p["title"] == title)


def resume(client: TestClient) -> str:
    return client.get("/api/resume/markdown").text


def orgs(client: TestClient) -> dict[str, str]:
    return {f["title"]: f["id"] for f in client.get("/api/facts", params={"kind": "Organization"}).json()}


@pytest.fixture
def client(tmp_path: Path):
    with TestClient(create_app(tmp_path)) as c:
        import_linkedin(c)
        yield c


def test_profile_is_nested_with_ids(client) -> None:
    profile = client.get("/api/profile").json()
    senior = position(client, "Senior Engineer")
    assert profile["id"] and profile["name"] == "Jane Doe" and senior["id"] and senior["organization"] == "Acme Corp"
    assert len(senior["achievement_ids"]) == len(senior["achievements"]) == 2
    assert len(profile["skill_ids"]) == len(profile["skills"])


def test_profile_exposes_the_organization_and_school_facts_so_they_can_be_edited(client) -> None:
    profile = client.get("/api/profile").json()
    orgs_by_name = orgs(client)
    assert position(client, "Senior Engineer")["organization_id"] == orgs_by_name["Acme Corp"]
    assert profile["education"][0]["school_id"] == orgs_by_name["University of Lisbon"]


def test_an_edit_survives_restart_and_reimport(client, tmp_path: Path) -> None:
    senior = position(client, "Senior Engineer")
    res = client.patch(f"/api/facts/{senior['id']}", json={"title": "Staff Engineer"})
    assert res.status_code == 200 and res.json()["title"] == "Staff Engineer"
    assert res.json()["attributes"] == senior["attributes"]  # omitted fields are kept
    assert "### Staff Engineer, Acme Corp" in resume(client)

    import_linkedin(client)
    assert "### Staff Engineer, Acme Corp" in resume(client)
    with TestClient(create_app(tmp_path)) as restarted:
        assert "### Staff Engineer, Acme Corp" in resume(restarted)
        assert "Senior Engineer" not in resume(restarted)


def test_attributes_are_replaced_in_full(client) -> None:
    senior = position(client, "Senior Engineer")
    res = client.patch(f"/api/facts/{senior['id']}", json={"attributes": {"period": "2001 - 2002"}})
    assert res.json()["attributes"] == {"period": "2001 - 2002"}
    assert "### Senior Engineer, Acme Corp (2001 - 2002)" in resume(client)


def test_hide_removes_a_bullet_and_unhide_restores_it(client) -> None:
    senior = position(client, "Senior Engineer")
    bullet_id, bullet = senior["achievement_ids"][0], senior["achievements"][0]
    client.patch(f"/api/facts/{bullet_id}", json={"attributes": {"hidden": "true"}})
    assert f"- {bullet}" not in resume(client)
    assert bullet not in position(client, "Senior Engineer")["achievements"]
    assert any(f["id"] == bullet_id for f in client.get("/api/facts").json())  # nothing is deleted
    client.patch(f"/api/facts/{bullet_id}", json={"attributes": {}})
    assert f"- {bullet}" in resume(client)


def test_unknown_fact_and_empty_title_are_rejected(client) -> None:
    assert client.patch("/api/facts/nope", json={"title": "x"}).status_code == 404
    senior = position(client, "Senior Engineer")
    assert client.patch(f"/api/facts/{senior['id']}", json={"title": ""}).status_code == 422


def test_manual_add_builds_position_bullet_and_skill(client, tmp_path: Path) -> None:
    person = client.get("/api/profile").json()["id"]
    res = client.post("/api/facts", json={"kind": "Position", "title": "Consultant", "parent_id": person,
                                          "attributes": {"organization": "Initech", "period": "2024 - 2025"}})
    assert res.status_code == 201
    consultant = res.json()["id"]
    client.post("/api/facts", json={"kind": "Achievement", "title": "Saved the day", "parent_id": consultant})
    client.post("/api/facts", json={"kind": "Skill", "title": "Rust", "parent_id": person})
    md = resume(client)
    assert "### Consultant, Initech (2024 - 2025)\n- Saved the day" in md and "Rust" in md
    manual = [f for f in client.get("/api/facts", params={"kind": "Position"}).json() if f["id"] == consultant]
    assert manual[0]["source"] == "manual" and "organization" not in manual[0]["attributes"]
    with TestClient(create_app(tmp_path)) as restarted:
        assert "- Saved the day" in resume(restarted)


@pytest.mark.parametrize(
    ("body", "status"),
    [({"kind": "Position", "title": "X", "parent_id": "nope"}, 404),
     ({"kind": "Position", "title": "X"}, 422),  # a position needs a person
     ({"kind": "Achievement", "title": "X", "parent_id": "PERSON"}, 422),  # not under a person
     ({"kind": "Skill", "title": "  ", "parent_id": "PERSON"}, 422),
     ({"kind": "Wizard", "title": "X"}, 422)],
)
def test_manual_add_validation(client, body, status) -> None:
    person = client.get("/api/profile").json()["id"]
    body = {k: person if v == "PERSON" else v for k, v in body.items()}
    assert client.post("/api/facts", json=body).status_code == status


def test_acme_corp_and_acme_are_proposed_merged_and_the_merge_is_undone(client, tmp_path: Path) -> None:
    assert client.get("/api/duplicates").json() == []
    import_resume_file(client)
    assert "### Platform Lead, Acme (2020 - 2021)" in resume(client)

    ids = orgs(client)
    [dup] = client.get("/api/duplicates").json()
    assert dup["kind"] == "Organization" and {dup["a"]["title"], dup["b"]["title"]} == {"Acme Corp", "Acme"}
    assert dup["score"] >= 0.9

    merge = {"alias_id": ids["Acme"], "canonical_id": ids["Acme Corp"]}
    assert client.post("/api/merges", json=merge).status_code == 200
    md = resume(client)
    assert "### Platform Lead, Acme Corp (2020 - 2021)" in md and "### Senior Engineer, Acme Corp" in md
    assert ", Acme (" not in md
    assert "Acme" not in orgs(client) and client.get("/api/duplicates").json() == []

    import_resume_file(client)  # a re-import does not resurrect the alias
    assert ", Acme (" not in resume(client)
    with TestClient(create_app(tmp_path)) as restarted:
        assert ", Acme (" not in resume(restarted)

    assert client.post("/api/merges", json={**merge, "undo": True}).status_code == 200
    md = resume(client)
    assert "### Platform Lead, Acme (2020 - 2021)" in md and "### Senior Engineer, Acme Corp" in md
    assert len(client.get("/api/duplicates").json()) == 1


def test_duplicate_positions_are_proposed_and_stay_so_after_the_employers_merge(client) -> None:
    client.post("/api/import/text", json={"text": "Jane Doe\n\nExperience\nSenior Engineer at Acme, 2020 - 2021\n"})
    kinds = lambda: sorted(d["kind"] for d in client.get("/api/duplicates").json())
    assert kinds() == ["Organization", "Position"]  # similar employers count as matching
    ids = orgs(client)
    client.post("/api/merges", json={"alias_id": ids["Acme"], "canonical_id": ids["Acme Corp"]})
    assert kinds() == ["Position"]


def test_merge_validation(client) -> None:
    import_resume_file(client)
    ids = orgs(client)
    person = client.get("/api/profile").json()["id"]
    post = lambda **body: client.post("/api/merges", json=body).status_code
    assert post(alias_id="nope", canonical_id=ids["Acme"]) == 404
    assert post(alias_id=ids["Acme"], canonical_id="nope") == 404
    assert post(alias_id=ids["Acme"], canonical_id=ids["Acme"]) == 422
    assert post(alias_id=ids["Acme"], canonical_id=person) == 422
    assert post(alias_id=ids["Acme"], canonical_id=ids["Globex"], undo=True) == 404  # nothing to undo


def bullets(client: TestClient) -> list[str]:
    return position(client, "Senior Engineer")["achievements"]


def test_bullets_sort_by_order_when_set_and_keep_import_order_otherwise(client, tmp_path: Path) -> None:
    senior = position(client, "Senior Engineer")
    first, second = senior["achievement_ids"]
    cut, kube = senior["achievements"]
    assert bullets(client) == [cut, kube]

    assert client.patch(f"/api/facts/{second}/order", json={"order": 1}).status_code == 200
    assert bullets(client) == [kube, cut]  # an ordered bullet goes before unordered ones
    res = client.patch(f"/api/facts/{first}/order", json={"order": 2})
    assert res.json()["attributes"]["order"] == "2" and bullets(client) == [kube, cut]
    client.patch(f"/api/facts/{first}/order", json={"order": 0})
    assert bullets(client) == [cut, kube]

    client.post("/api/facts", json={"kind": "Achievement", "title": "Added later", "parent_id": senior["id"]})
    assert bullets(client) == [cut, kube, "Added later"]  # no order: after the ordered ones, in import order
    assert f"- {cut}\n- {kube}\n- Added later" in resume(client)
    with TestClient(create_app(tmp_path)) as restarted:
        assert position(restarted, "Senior Engineer")["achievements"] == [cut, kube, "Added later"]


def test_setting_the_order_keeps_the_other_attributes_and_validates(client) -> None:
    senior = position(client, "Senior Engineer")
    bullet = senior["achievement_ids"][0]
    client.patch(f"/api/facts/{bullet}", json={"attributes": {"note": "kept"}})
    res = client.patch(f"/api/facts/{bullet}/order", json={"order": 3})
    assert res.json()["attributes"] == {"note": "kept", "order": "3"}
    assert client.patch("/api/facts/nope/order", json={"order": 1}).status_code == 404
    assert client.patch(f"/api/facts/{bullet}/order", json={"order": -1}).status_code == 422
    assert client.patch(f"/api/facts/{bullet}/order", json={"order": "first"}).status_code == 422


def test_a_dismissed_pair_is_no_longer_proposed_and_stays_so_after_re_import_and_restart(client, tmp_path: Path) -> None:
    import_resume_file(client)
    [dup] = client.get("/api/duplicates").json()
    pair = {"a_id": dup["b"]["id"], "b_id": dup["a"]["id"]}  # either order names the same pair
    assert client.post("/api/duplicates/dismiss", json=pair).status_code == 200
    assert client.get("/api/duplicates").json() == []
    import_resume_file(client)
    assert client.get("/api/duplicates").json() == []
    with TestClient(create_app(tmp_path)) as restarted:
        assert restarted.get("/api/duplicates").json() == []
        assert "### Platform Lead, Acme (2020 - 2021)" in resume(restarted)  # dismissing merges nothing


def test_dismiss_validation(client) -> None:
    import_resume_file(client)
    ids = orgs(client)
    post = lambda a, b: client.post("/api/duplicates/dismiss", json={"a_id": a, "b_id": b}).status_code
    assert post("nope", ids["Acme"]) == 404
    assert post(ids["Acme"], ids["Acme"]) == 422
