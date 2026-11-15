"""Object store on the local filesystem. Keys are relative POSIX paths under one directory."""

from __future__ import annotations

import re
from pathlib import Path

from career_graph.application.ports import ObjectNotFound

_SEGMENT = re.compile(r"(?!\.+$)[\w.\- ]*[\w\-]")  # no "." / ".." segments, no trailing dot or space
_DEVICE = re.compile(r"(con|prn|aux|nul|com\d|lpt\d)(\..*)?$", re.IGNORECASE)


class LocalObjectStore:
    def __init__(self, root: Path) -> None:
        self._root = root.resolve()

    def _path(self, key: str) -> Path:
        # Allowlist per segment: it also keeps out the names Windows rejects or silently rewrites
        # (":" and other reserved characters, trailing dots and spaces, device names such as NUL).
        if ".." in key or not all(_SEGMENT.fullmatch(p) and not _DEVICE.match(p) for p in key.split("/")):
            raise ValueError(f"Invalid object key: {key!r}")
        path = (self._root / key).resolve()
        if self._root not in path.parents:  # backstop, e.g. a symlink inside the store
            raise ValueError(f"Invalid object key: {key!r}")
        return path

    def put(self, key: str, data: bytes, content_type: str) -> None:  # content_type is not kept: files have no metadata
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get(self, key: str) -> bytes:
        try:
            return self._path(key).read_bytes()
        except FileNotFoundError as error:
            raise ObjectNotFound(key) from error

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)
