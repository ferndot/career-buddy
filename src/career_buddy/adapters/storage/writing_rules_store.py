"""A person's own general writing rules per document kind, in `writing-rules.json` in the data folder. A kind with none saved uses the defaults."""

from __future__ import annotations

import json
from pathlib import Path

from career_buddy.domain.writing_rules import DEFAULT_RULES


class WritingRulesStore:
    def __init__(self, data_dir: Path) -> None:
        self._file = data_dir / "writing-rules.json"

    def _read(self) -> dict[str, list[str]]:
        return json.loads(self._file.read_text(encoding="utf-8")) if self._file.exists() else {}

    def custom(self, kind: str) -> tuple[str, ...]:
        """The saved override, empty when there is none."""
        return tuple(self._read().get(kind, ()))

    def rules(self, kind: str) -> tuple[str, ...]:
        """The rules the writer uses: the override, else the default."""
        return self.custom(kind) or DEFAULT_RULES[kind]  # type: ignore[index]

    def save(self, kind: str, rules: list[str]) -> None:
        """An empty list clears the override."""
        kept = {k: v for k, v in self._read().items() if k != kind}
        self._file.write_text(json.dumps(kept | ({kind: rules} if rules else {}), ensure_ascii=False), encoding="utf-8")
