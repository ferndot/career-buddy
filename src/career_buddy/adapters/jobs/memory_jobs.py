"""In-memory job state. shortcut: lost on restart (sources then read as ready), swap in a file or DB adapter to keep it."""

from __future__ import annotations

from career_buddy.application.ports import JobState


class InMemoryJobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, JobState] = {}

    def get(self, source: str) -> JobState | None:
        return self._jobs.get(source)

    def put(self, source: str, state: JobState) -> None:
        self._jobs[source] = state

    def delete(self, source: str) -> None:
        self._jobs.pop(source, None)

    def all(self) -> dict[str, JobState]:
        return dict(self._jobs)
