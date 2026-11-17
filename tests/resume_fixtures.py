"""A synthetic resume shaped like the text pdfminer gives for a real company-grouped PDF. Fictional people only.

Glyph bullets and separators arrive as U+FFFD, and the phone has lost its opening parenthesis in some files.
"""

from html import escape

FFFD = "�"
SEP = f" {FFFD} "


def resume_text(phone: str = "(206) 555-0142") -> str:
    return "\n".join([
        "Mira Valdane",
        "Principal Engineer and Platform Lead",
        SEP.join(["Lakeside, WA", "mira.valdane@example.com", phone]),
        "EXPERIENCE",
        "Northwind Labs / Contoso Works  Mar 2019 – Present",
        "Principal Software Engineer / Product Engineer",
        f"{FFFD} Led the platform rewrite",
        f"{FFFD} Cut deploy time by 60%",
        "Staff Engineer",
        f"{FFFD} Mentored five engineers",
        f"Fabrikam Systems  Jun 2014 {FFFD} Feb 2019",
        "Software Engineer",
        f"{FFFD} Built the billing pipeline",
        "EDUCATION",
        "Lakeside University",
        "BSc Computer Science",
        "2014 – 2017",
        "Harbor College",
        "MSc Data Engineering",
        "2017 – 2019",
        "SKILLS",
        "Languages",
        SEP.join(["Python", "Go", "SQL"]),
        "Cloud, Data & Tools",
        f"AWS, Postgres{SEP}Kafka",
        "Concepts",
        SEP.join(["Distributed systems", "API design"]),
        "AI & Machine Learning:",
        "Frameworks & Libraries",
        "FastAPI, Pydantic",
    ])


def resume_html() -> str:
    """The same lines as one paragraph each, so a PDF made from it reads back line for line."""
    body = "".join(f"<p>{escape(line)}</p>" for line in resume_text().splitlines())
    return f"<style>body{{margin:0;font:10pt/16px Arial}}p{{margin:0}}</style>{body}"
