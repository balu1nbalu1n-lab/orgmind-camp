"""
docx_export.py - Export an OrgMind answer (markdown) to an editable Word document.

Shared by OrgMind1 and OrgMind2. Requires: python-docx

Usage in Streamlit:
    from docx_export import generate_docx
    docx_bytes = generate_docx(question, result["answer"], result["sources"],
                               department, model_name)
    st.download_button("Download as Word", data=docx_bytes,
                       file_name="orgmind_response.docx",
                       mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
"""
import re
from io import BytesIO
from datetime import datetime

from docx import Document
from docx.shared import Pt, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

NAVY = RGBColor(0x1E, 0x27, 0x61)
GREY = RGBColor(0x66, 0x66, 0x66)
FONT = "Calibri"

_INLINE = re.compile(r"(\*\*\*.+?\*\*\*|\*\*.+?\*\*|\*.+?\*|`.+?`)")


def _strip_trailing_sources_line(answer_md):
    pattern = re.compile(r"\n*\*{0,2}Sources? consulted:?\*{0,2}.*$", re.IGNORECASE | re.DOTALL)
    return pattern.sub("", answer_md).strip()


def _add_runs(paragraph, text, size=None, color=None, bold_all=False):
    """Add text to a paragraph, honouring **bold**, *italic*, `code`."""
    for part in _INLINE.split(text):
        if not part:
            continue
        bold = italic = code = False
        if part.startswith("***") and part.endswith("***") and len(part) > 6:
            part, bold, italic = part[3:-3], True, True
        elif part.startswith("**") and part.endswith("**") and len(part) > 4:
            part, bold = part[2:-2], True
        elif part.startswith("*") and part.endswith("*") and len(part) > 2:
            part, italic = part[1:-1], True
        elif part.startswith("`") and part.endswith("`") and len(part) > 2:
            part, code = part[1:-1], True
        run = paragraph.add_run(part)
        run.bold = bold or bold_all
        run.italic = italic
        run.font.name = "Consolas" if code else FONT
        if size:
            run.font.size = Pt(size)
        if color is not None:
            run.font.color.rgb = color


def _shade(cell, hex_fill):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_fill)
    tcPr.append(shd)


def _split_row(line):
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [c.strip() for c in line.split("|")]


def _is_sep(line):
    return bool(re.match(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$", line))


def _add_table(doc, rows):
    ncols = max(len(r) for r in rows)
    table = doc.add_table(rows=len(rows), cols=ncols)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, row in enumerate(rows):
        for j in range(ncols):
            cell = table.cell(i, j)
            cell.text = ""
            p = cell.paragraphs[0]
            txt = row[j] if j < len(row) else ""
            if i == 0:
                _add_runs(p, txt, size=10, color=RGBColor(0xFF, 0xFF, 0xFF), bold_all=True)
                _shade(cell, "1E2761")
            else:
                _add_runs(p, txt, size=10)
                if i % 2 == 0:
                    _shade(cell, "F2F4F9")
    doc.add_paragraph()


def _render_markdown(doc, md):
    lines = md.replace("\r\n", "\n").split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        # Table: header row followed by separator row
        if "|" in stripped and i + 1 < len(lines) and _is_sep(lines[i + 1]):
            rows = [_split_row(stripped)]
            i += 2
            while i < len(lines) and "|" in lines[i] and lines[i].strip():
                rows.append(_split_row(lines[i]))
                i += 1
            _add_table(doc, rows)
            continue

        m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if m:
            level = min(len(m.group(1)), 3)
            h = doc.add_heading(level=level)
            _add_runs(h, m.group(2), color=NAVY)
            i += 1
            continue

        if re.match(r"^[-*_]{3,}$", stripped):
            i += 1
            continue

        m = re.match(r"^(\s*)[-*+]\s+(.*)$", line)
        if m:
            indent = len(m.group(1).replace("\t", "    "))
            style = "List Bullet 2" if indent >= 2 else "List Bullet"
            p = doc.add_paragraph(style=style)
            _add_runs(p, m.group(2))
            i += 1
            continue

        m = re.match(r"^(\s*)\d+[.)]\s+(.*)$", line)
        if m:
            indent = len(m.group(1).replace("\t", "    "))
            style = "List Number 2" if indent >= 2 else "List Number"
            p = doc.add_paragraph(style=style)
            _add_runs(p, m.group(2))
            i += 1
            continue

        # Paragraph: gather consecutive plain lines
        buf = [stripped]
        i += 1
        while i < len(lines):
            nxt = lines[i].strip()
            if (not nxt or re.match(r"^(#{1,6}\s|[-*+]\s|\d+[.)]\s)", nxt)
                    or ("|" in nxt and i + 1 < len(lines) and _is_sep(lines[i + 1]))):
                break
            buf.append(nxt)
            i += 1
        p = doc.add_paragraph()
        _add_runs(p, " ".join(buf))


def generate_docx(question, answer_md, sources, department, model_name,
                  system_name="OrgMind — CAMP Institutional Memory"):
    """Return .docx bytes for one question/answer."""
    doc = Document()

    for s in doc.sections:
        s.left_margin = s.right_margin = Cm(2.2)
        s.top_margin = s.bottom_margin = Cm(2.0)

    normal = doc.styles["Normal"]
    normal.font.name = FONT
    normal.font.size = Pt(11)
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
    for name in ("Heading 1", "Heading 2", "Heading 3"):
        st = doc.styles[name]
        st.font.name = FONT
        st.font.color.rgb = NAVY
        st.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)

    # Title block
    t = doc.add_paragraph()
    _add_runs(t, system_name, size=18, color=NAVY, bold_all=True)
    meta = doc.add_paragraph()
    _add_runs(meta,
              f"Department: {department}   |   Model: {model_name}   |   "
              f"Generated: {datetime.now().strftime('%d %b %Y, %H:%M')}",
              size=9, color=GREY)

    doc.add_heading("Question", level=2)
    q = doc.add_paragraph()
    _add_runs(q, question)

    doc.add_heading("Response", level=2)
    _render_markdown(doc, _strip_trailing_sources_line(answer_md))

    if sources:
        doc.add_heading("Documents Consulted", level=2)
        seen = []
        for s in sources:
            name = s if isinstance(s, str) else (
                s.get("source") or s.get("name") or s.get("file") or str(s))
            if name not in seen:
                seen.append(name)
        for name in seen:
            p = doc.add_paragraph(style="List Bullet")
            _add_runs(p, name, size=10)

    note = doc.add_paragraph()
    _add_runs(note, "AI-generated from the CAMP knowledge base. Please verify against "
                    "the source documents before relying on this content.",
              size=8, color=GREY)

    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()
