"""Key storage: the OS keychain first, a private file when it is not available or the file store is asked for."""

import json
from pathlib import Path

import keyring
import pytest
from keyring.backend import KeyringBackend

from career_buddy.adapters.storage.key_store import KeyStore


class MemoryKeychain(KeyringBackend):
    priority = 1

    def __init__(self) -> None:
        self.items: dict[tuple[str, str], str] = {}

    def set_password(self, service: str, username: str, password: str) -> None:
        self.items[(service, username)] = password

    def get_password(self, service: str, username: str) -> str | None:
        return self.items.get((service, username))

    def delete_password(self, service: str, username: str) -> None:
        self.items.pop((service, username), None)


@pytest.fixture
def keychain(monkeypatch: pytest.MonkeyPatch):
    previous = keyring.get_keyring()
    fake = MemoryKeychain()
    keyring.set_keyring(fake)
    monkeypatch.delenv("CAREER_BUDDY_KEY_STORE", raising=False)
    yield fake
    keyring.set_keyring(previous)


def test_keys_go_to_the_os_keychain_when_there_is_one_and_never_to_disk(tmp_path: Path, keychain: MemoryKeychain) -> None:
    store = KeyStore(tmp_path)
    assert store.kind == "keychain"
    store.set("abc", "fake-key-1")
    assert store.get("abc") == "fake-key-1" and list(keychain.items.values()) == ["fake-key-1"]
    assert not (tmp_path / "secrets.json").exists()
    store.delete("abc")
    assert store.get("abc") is None and not keychain.items


def test_the_file_store_is_used_when_asked_for_and_deleting_removes_the_key(tmp_path: Path, keychain: MemoryKeychain, monkeypatch) -> None:
    monkeypatch.setenv("CAREER_BUDDY_KEY_STORE", "file")
    store = KeyStore(tmp_path)
    assert store.kind == "file"
    store.set("abc", "fake-key-1")
    store.set("def", "fake-key-2")
    assert json.loads((tmp_path / "secrets.json").read_text()) == {"abc": "fake-key-1", "def": "fake-key-2"}
    assert not keychain.items
    store.delete("abc")
    assert KeyStore(tmp_path).get("abc") is None and KeyStore(tmp_path).get("def") == "fake-key-2"


def test_the_file_store_is_the_fallback_when_no_keychain_works(tmp_path: Path, monkeypatch) -> None:
    from keyring.backends.fail import Keyring as NoKeychain

    previous = keyring.get_keyring()
    keyring.set_keyring(NoKeychain())
    monkeypatch.delenv("CAREER_BUDDY_KEY_STORE", raising=False)
    try:
        assert KeyStore(tmp_path).kind == "file"
    finally:
        keyring.set_keyring(previous)
