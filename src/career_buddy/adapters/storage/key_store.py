"""API keys, kept apart from the settings file. The OS keychain first; a private file when there is none."""

from __future__ import annotations

import json
import os
from pathlib import Path

import keyring
from keyring.backends.fail import Keyring as NoKeychain
from keyring.errors import KeyringError

SERVICE = "career-buddy"


class KeyStore:
    def __init__(self, data_dir: Path) -> None:
        self._file = data_dir / "secrets.json"
        file_only = os.environ.get("CAREER_BUDDY_KEY_STORE") == "file" or isinstance(keyring.get_keyring(), NoKeychain)
        self.kind = "file" if file_only else "keychain"

    def get(self, conn_id: str) -> str | None:
        if self.kind == "keychain":
            return keyring.get_password(SERVICE, conn_id)
        return self._read().get(conn_id)

    def set(self, conn_id: str, key: str) -> None:
        if self.kind == "keychain":
            keyring.set_password(SERVICE, conn_id, key)
        else:
            self._write(self._read() | {conn_id: key})

    def delete(self, conn_id: str) -> None:
        if self.kind == "keychain":
            try:
                keyring.delete_password(SERVICE, conn_id)
            except KeyringError:  # nothing saved under that id
                pass
        else:
            self._write({k: v for k, v in self._read().items() if k != conn_id})

    def _read(self) -> dict[str, str]:
        return json.loads(self._file.read_text()) if self._file.exists() else {}

    def _write(self, secrets: dict[str, str]) -> None:
        # shortcut: plain text, mode 0600 (not enforced on Windows). The UI says so; use the keychain for encryption.
        tmp = self._file.with_suffix(".tmp")
        descriptor = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "w") as handle:
            json.dump(secrets, handle)
        tmp.replace(self._file)
