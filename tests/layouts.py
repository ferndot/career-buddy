"""Resume files generated at test time, so no binaries are checked in. PDFs need Chromium (use the `chromium` fixture)."""

import base64
import io

from docx import Document
from docx.oxml import parse_xml
from playwright.sync_api import sync_playwright

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
PIXEL = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNgYGD4DwABBAEAwS2OUAAAAABJRU5ErkJggg=="
)

# Two columns whose cells are painted row by row (left, right, left, right...), so the PDF content stream
# interleaves them and only layout analysis can recover left-column-then-right-column order.
TWO_COLUMNS = """<style>
body{margin:0;font:10pt/16px Arial}
p{margin:0}
.page{display:grid;grid-template-columns:1fr 1fr;column-gap:60px}
.wide{grid-column:1/-1}
</style><div class="page">
<p class="wide">Jane Doe</p><p class="wide">Experience</p>
<p>Senior Engineer at Acme Corp, 2019 - 2023</p><p>Engineer at Globex, 2015 - 2019</p>
<p>● Cut build times by 60%</p><p>● Built the billing pipeline</p>
<p>● Led a team of 8 engineers</p><p>● Mentored 5 interns</p>
<p>&nbsp;</p><p>Skills</p>
<p>&nbsp;</p><p>Python, Go</p></div>"""

IMAGE_ONLY = f'<img src="data:image/png;base64,{PIXEL}" style="width:400px;height:400px">'


def pdf(html: str) -> bytes:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page()
            page.set_content(html)
            return page.pdf(format="Letter", margin={s: "0.75in" for s in ("top", "right", "bottom", "left")})
        finally:
            browser.close()


def resume_docx() -> bytes:
    """Contact info in the header, skills in a table, education in a text box, a stacked Org/Title/dates entry."""
    doc = Document()
    doc.sections[0].header.paragraphs[0].text = "jane@example.com | +351 912 345 678"
    for line in ("Jane Doe", "Experience", "Acme Corp", "Senior Engineer", "Mar 2019 - Present",
                 "● Cut build times by 60%", "Skills"):
        doc.add_paragraph(line)
    row = doc.add_table(rows=1, cols=3).rows[0]
    for cell, skill in zip(row.cells, ("Python", "Go", "SQL")):
        cell.text = skill
    doc.add_paragraph("Education")
    doc.add_paragraph()._p.append(parse_xml(
        f'<w:r xmlns:w="{W}" xmlns:v="urn:schemas-microsoft-com:vml"><w:pict><v:shape><v:textbox>'
        "<w:txbxContent><w:p><w:r><w:t>University of Lisbon</w:t></w:r></w:p></w:txbxContent>"
        "</v:textbox></v:shape></w:pict></w:r>"
    ))
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
