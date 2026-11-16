"""LocalObjectStore: round trip, missing keys, and keys that try to leave the store directory."""

from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from career_buddy.adapters.storage.local_object_store import LocalObjectStore
from career_buddy.application.ports import ObjectNotFound


@pytest.fixture
def store(tmp_path: Path) -> LocalObjectStore:
    return LocalObjectStore(tmp_path / "objects")


def test_round_trip(store) -> None:
    assert not store.exists("sources/a.txt")
    store.put("sources/a.txt", b"hello", "text/plain")
    assert store.exists("sources/a.txt")
    assert store.get("sources/a.txt") == b"hello"


def test_put_overwrites(store) -> None:
    store.put("k", b"one", "text/plain")
    store.put("k", b"two", "text/plain")
    assert store.get("k") == b"two"


def test_delete_removes_and_is_idempotent(store) -> None:
    store.put("k", b"x", "text/plain")
    store.delete("k")
    store.delete("k")
    assert not store.exists("k")


def test_missing_key_raises_object_not_found(store) -> None:
    with pytest.raises(ObjectNotFound):
        store.get("sources/nope.txt")


@pytest.mark.parametrize(
    "key", ["", "/etc/passwd", "../x", "a/../../x", "a/..", "a\\b", "..\\x", "C:/x", "C:x", "a//b", "a/", "./a", "a\x00b"]
)
def test_bad_keys_are_rejected_by_every_operation(store, key) -> None:
    for call in (lambda: store.put(key, b"x", "text/plain"), lambda: store.get(key), lambda: store.exists(key), lambda: store.delete(key)):
        with pytest.raises(ValueError):
            call()


def _files(root: Path) -> list[Path]:
    return [p for p in root.rglob("*") if p.is_file()]


@settings(max_examples=300, deadline=None)
@given(st.text(max_size=40))
def test_any_key_is_either_rejected_or_stays_inside_the_store(tmp_path_factory, key) -> None:
    root = tmp_path_factory.mktemp("store") / "objects"
    store = LocalObjectStore(root)
    try:
        store.put(key, b"data", "text/plain")
    except ValueError:
        assert not _files(root.parent) or all(root in p.parents for p in _files(root.parent))
        return
    assert store.get(key) == b"data"
    assert all(root in p.parents for p in _files(root.parent))


@settings(max_examples=200, deadline=None)
@given(st.text(max_size=10), st.sampled_from(["..", "\\"]), st.text(max_size=10))
def test_keys_containing_dotdot_or_backslash_are_always_rejected(tmp_path_factory, head, marker, tail) -> None:
    store = LocalObjectStore(tmp_path_factory.mktemp("store") / "objects")
    with pytest.raises(ValueError):
        store.put(head + marker + tail, b"x", "text/plain")


@settings(max_examples=100, deadline=None)
@given(st.text(max_size=20))
def test_absolute_keys_are_always_rejected(tmp_path_factory, rest) -> None:
    store = LocalObjectStore(tmp_path_factory.mktemp("store") / "objects")
    with pytest.raises(ValueError):
        store.put("/" + rest, b"x", "text/plain")


def test_list_returns_sorted_keys_under_a_prefix(store) -> None:
    for key in ("documents/b/meta.json", "documents/a/file.pdf", "documents/a/meta.json", "sources/x.txt", "documentsx/y"):
        store.put(key, b"x", "text/plain")
    assert store.list("documents/a/") == ["documents/a/file.pdf", "documents/a/meta.json"]
    assert store.list("documents/") == ["documents/a/file.pdf", "documents/a/meta.json", "documents/b/meta.json"]
    assert store.list("") == sorted(["documents/a/file.pdf", "documents/a/meta.json", "documents/b/meta.json", "documentsx/y", "sources/x.txt"])
    assert store.list("nothing/") == [] and store.list("sources/x") == ["sources/x.txt"]


def test_list_rejects_a_prefix_that_leaves_the_store(store) -> None:
    with pytest.raises(ValueError):
        store.list("../")
