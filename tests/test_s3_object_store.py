"""S3ObjectStore against moto's in-process fake S3."""

import boto3
import pytest
from moto import mock_aws

from career_buddy.adapters.storage.s3_object_store import S3ObjectStore
from career_buddy.application.ports import ObjectNotFound

CONFIG = dict(endpoint_url="http://minio.test:9000", access_key="k", secret_key="s", region="us-east-1")


def raw_client(region: str = "us-east-1"):
    return boto3.client("s3", region_name=region, endpoint_url=CONFIG["endpoint_url"],
                        aws_access_key_id="k", aws_secret_access_key="s")


@pytest.fixture
def store():
    with mock_aws():
        yield S3ObjectStore(bucket="careers", **CONFIG)


def test_round_trip_keeps_bytes_and_content_type(store) -> None:
    assert not store.exists("sources/a.txt")
    store.put("sources/a.txt", b"hello", "text/plain")
    assert store.exists("sources/a.txt")
    assert store.get("sources/a.txt") == b"hello"
    assert raw_client().head_object(Bucket="careers", Key="sources/a.txt")["ContentType"] == "text/plain"


def test_missing_key_raises_object_not_found(store) -> None:
    with pytest.raises(ObjectNotFound):
        store.get("sources/nope.txt")


def test_delete_removes_and_is_idempotent(store) -> None:
    store.put("k", b"x", "text/plain")
    store.delete("k")
    store.delete("k")
    assert not store.exists("k")


def test_bucket_is_created_on_startup() -> None:
    with mock_aws():
        assert raw_client().list_buckets()["Buckets"] == []
        S3ObjectStore(bucket="careers", **CONFIG)
        assert [b["Name"] for b in raw_client().list_buckets()["Buckets"]] == ["careers"]


def test_existing_bucket_and_its_objects_are_left_alone() -> None:
    with mock_aws():
        S3ObjectStore(bucket="careers", **CONFIG).put("k", b"x", "text/plain")
        assert S3ObjectStore(bucket="careers", **CONFIG).get("k") == b"x"


def test_bucket_is_created_in_a_non_default_region() -> None:
    with mock_aws():
        S3ObjectStore(bucket="careers", **{**CONFIG, "region": "eu-west-1"})
        assert raw_client("eu-west-1").get_bucket_location(Bucket="careers")["LocationConstraint"] == "eu-west-1"


def test_list_returns_keys_under_a_prefix_across_pages(store) -> None:
    for i in range(1100):  # S3 answers at most 1000 keys a page
        store.put(f"documents/{i:04d}/meta.json", b"x", "application/json")
    store.put("sources/a.txt", b"x", "text/plain")
    keys = store.list("documents/")
    assert len(keys) == 1100 and keys[0] == "documents/0000/meta.json"
    assert store.list("documents/0007/") == ["documents/0007/meta.json"]
    assert store.list("nothing/") == []
