"""S3ObjectStore against a real S3 server (MinIO, SeaweedFS). Runs only when CAREER_GRAPH_S3_ENDPOINT is set."""

import os
import uuid

import pytest

from career_graph.adapters.storage.s3_object_store import S3ObjectStore
from career_graph.application.ports import ObjectNotFound

pytestmark = pytest.mark.skipif(
    not os.environ.get("CAREER_GRAPH_S3_ENDPOINT"),
    reason="needs a real S3 server (docker compose --profile storage up s3, or your own MinIO): set CAREER_GRAPH_S3_ENDPOINT (and _BUCKET, _ACCESS_KEY, _SECRET_KEY, optionally _REGION)",
)


def test_round_trip_against_minio() -> None:
    env = os.environ
    store = S3ObjectStore(env["CAREER_GRAPH_S3_ENDPOINT"], env["CAREER_GRAPH_S3_BUCKET"], env["CAREER_GRAPH_S3_ACCESS_KEY"],
                          env["CAREER_GRAPH_S3_SECRET_KEY"], env.get("CAREER_GRAPH_S3_REGION", "us-east-1"))
    key = f"tests/{uuid.uuid4().hex}.txt"  # its own key, so a bucket with real data in it is left alone
    try:
        assert not store.exists(key)
        store.put(key, b"hello", "text/plain")
        assert store.exists(key) and store.get(key) == b"hello"
    finally:
        store.delete(key)
    assert not store.exists(key)
    with pytest.raises(ObjectNotFound):
        store.get(key)
