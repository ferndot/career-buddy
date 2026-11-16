"""POST /api/import/file keeps the original bytes in the object store and records the key in the import event."""

import hashlib
import json
from pathlib import Path

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws

from career_buddy.web.app import create_app

TEXT = b"Ada Lovelace\n\nExperience\nAnalyst at Analytical Society, 2010 - 2015\n- Wrote the first algorithm\n"
KEY = f"sources/{hashlib.sha256(TEXT).hexdigest()}.txt"
ENDPOINT = "http://minio.test:9000"  # answered by moto, see conftest


def upload(client: TestClient, name: str = "resume.txt", data: bytes = TEXT):
    return client.post("/api/import/file", files={"file": (name, data, "application/octet-stream")})


def logged_keys(data_dir: Path) -> list[str]:
    records = [json.loads(line) for line in (data_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    return [r.get("source_key", "") for r in records if r["type"] == "FactsImported"]


@pytest.fixture
def local(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("CAREER_BUDDY_STORAGE", raising=False)
    with TestClient(create_app(tmp_path)) as client:
        yield client


@pytest.fixture
def s3(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    for name, value in {"STORAGE": "s3", "S3_ENDPOINT": ENDPOINT, "S3_BUCKET": "careers",
                        "S3_ACCESS_KEY": "k", "S3_SECRET_KEY": "s"}.items():
        monkeypatch.setenv(f"CAREER_BUDDY_{name}", value)
    monkeypatch.delenv("CAREER_BUDDY_S3_REGION", raising=False)
    with mock_aws(), TestClient(create_app(tmp_path)) as client:
        yield client


def bucket_client():
    return boto3.client("s3", region_name="us-east-1", endpoint_url=ENDPOINT,
                        aws_access_key_id="k", aws_secret_access_key="s")


def test_local_storage_is_the_default_and_keeps_the_original_bytes(local, tmp_path: Path) -> None:
    assert upload(local).json() == {"facts": 4}
    assert (tmp_path / "objects" / KEY).read_bytes() == TEXT
    assert logged_keys(tmp_path) == [KEY]


def test_the_key_depends_on_the_bytes_and_the_extension_not_the_file_name(local, tmp_path: Path) -> None:
    upload(local, "one.txt")
    upload(local, "two.txt")
    upload(local, "three.md")
    assert logged_keys(tmp_path)[:2] == [KEY, KEY]
    assert logged_keys(tmp_path)[2] == KEY.replace(".txt", ".md")


def test_an_existing_key_is_not_written_again(local, tmp_path: Path) -> None:
    upload(local)
    before = (tmp_path / "objects" / KEY).stat().st_mtime_ns
    assert upload(local).json() == {"facts": 4}
    assert (tmp_path / "objects" / KEY).stat().st_mtime_ns == before


@pytest.mark.parametrize(("name", "data", "status"), [("resume.rtf", TEXT, 415), ("resume.txt", b" \n ", 422), ("r.docx", b"nope", 422)])
def test_rejected_uploads_store_nothing(local, tmp_path: Path, name, data, status) -> None:
    assert upload(local, name, data).status_code == status
    assert not (tmp_path / "objects").exists() or not list((tmp_path / "objects").rglob("*.*"))


def test_s3_storage_keeps_the_source_under_sources(s3, tmp_path: Path) -> None:
    assert upload(s3).json() == {"facts": 4}
    objects = bucket_client().list_objects_v2(Bucket="careers")["Contents"]
    assert [o["Key"] for o in objects] == [KEY]
    assert bucket_client().get_object(Bucket="careers", Key=KEY)["Body"].read() == TEXT
    assert logged_keys(tmp_path) == [KEY]
    assert not (tmp_path / "objects").exists()


def test_s3_uploading_the_same_file_twice_does_not_duplicate_or_rewrite_the_object(s3) -> None:
    bucket_client().put_bucket_versioning(Bucket="careers", VersioningConfiguration={"Status": "Enabled"})
    upload(s3)
    upload(s3, "again.txt")
    versions = bucket_client().list_object_versions(Bucket="careers")["Versions"]
    assert [v["Key"] for v in versions] == [KEY]


def test_unknown_storage_kind_fails_at_startup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CAREER_BUDDY_STORAGE", "floppy")
    with pytest.raises(ValueError, match="CAREER_BUDDY_STORAGE"), TestClient(create_app(tmp_path)):
        pass


def test_s3_storage_without_its_settings_names_the_missing_variable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CAREER_BUDDY_STORAGE", "s3")
    monkeypatch.delenv("CAREER_BUDDY_S3_ENDPOINT", raising=False)
    with pytest.raises(KeyError, match="CAREER_BUDDY_S3_ENDPOINT"), TestClient(create_app(tmp_path)):
        pass
