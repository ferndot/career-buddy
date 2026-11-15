"""Parses a LinkedIn "Get a copy of your data" export (CSV files, zipped or extracted)."""

from __future__ import annotations

import csv
import io
from pathlib import PurePosixPath

from career_graph.domain.builder import BatchBuilder
from career_graph.domain.model import FactBatch
from career_graph.domain.text import split_bullets


def _rows(files: dict[str, bytes], wanted: str) -> list[dict[str, str]]:
    for name, data in files.items():
        if PurePosixPath(name.replace("\\", "/")).name.lower() == wanted.lower():
            return list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"))))
    return []


class LinkedInExportParser:
    """Reads Profile, Positions, Skills and Education CSVs. Any file may be missing."""

    def parse(self, files: dict[str, bytes], source: str) -> FactBatch:
        b = BatchBuilder(source)
        profile = _rows(files, "Profile.csv")
        first = profile[0] if profile else {}
        name = f"{first.get('First Name', '')} {first.get('Last Name', '')}".strip() or "Me"
        person = b.person(
            name,
            headline=first.get("Headline", ""),
            summary=first.get("Summary", ""),
            location=first.get("Geo Location", ""),
        )

        for row in _rows(files, "Positions.csv"):
            bullets, prose = split_bullets(row.get("Description", ""))
            b.position(
                person,
                row.get("Title", ""),
                row.get("Company Name", ""),
                achievements=bullets,
                description=prose,
                location=row.get("Location", ""),
                started=row.get("Started On", ""),
                finished=row.get("Finished On", ""),
            )

        for row in _rows(files, "Skills.csv"):
            if row.get("Name", "").strip():
                b.skill(person, row["Name"])

        for row in _rows(files, "Education.csv"):
            b.education(
                person,
                row.get("School Name", ""),
                row.get("Degree Name", ""),
                started=row.get("Start Date", ""),
                finished=row.get("End Date", ""),
                notes=row.get("Notes", ""),
            )
        return b.build()
