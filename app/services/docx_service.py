from io import BytesIO
from urllib.parse import quote

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt

from app.models import Draft
from app.constants import STATUS_LABELS


def clean_filename(filename: str) -> str:
    allowed_characters = []

    for character in filename:
        if character.isalnum() or character in [" ", "_", "-", "."]:
            allowed_characters.append(character)

    cleaned = "".join(allowed_characters).strip()

    if not cleaned:
        return "draft.docx"

    if not cleaned.lower().endswith(".docx"):
        cleaned = f"{cleaned}.docx"

    return cleaned[:90]


def encode_docx_filename(filename: str) -> str:
    return quote(filename)


def add_multiline_text_to_docx(document: Document, text: str):
    lines = text.splitlines()

    for line in lines:
        stripped_line = line.strip()

        if not stripped_line:
            document.add_paragraph()
            continue

        if stripped_line.isupper() and len(stripped_line) < 90:
            paragraph = document.add_paragraph()
            run = paragraph.add_run(stripped_line)
            run.bold = True
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            continue

        if stripped_line.startswith(
            (
                "1.",
                "2.",
                "3.",
                "4.",
                "5.",
                "6.",
                "7.",
                "8.",
                "9.",
                "10.",
                "11.",
                "11.1",
                "11.2",
                "11.3",
            )
        ):
            paragraph = document.add_paragraph()
            run = paragraph.add_run(stripped_line)
            run.bold = True
            continue

        if stripped_line.startswith(("•", "-", "·")):
            document.add_paragraph(stripped_line, style="List Bullet")
            continue

        document.add_paragraph(stripped_line)


def build_draft_docx(draft: Draft) -> BytesIO:
    document = Document()

    styles = document.styles

    normal_style = styles["Normal"]
    normal_style.font.name = "Times New Roman"
    normal_style.font.size = Pt(12)

    title = document.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_run = title.add_run("РАБОЧАЯ ПРОГРАММА ДИСЦИПЛИНЫ")
    title_run.bold = True
    title_run.font.name = "Times New Roman"
    title_run.font.size = Pt(14)

    document.add_paragraph()

    course_title = document.add_paragraph()
    course_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    course_run = course_title.add_run(draft.course.title)
    course_run.bold = True
    course_run.font.name = "Times New Roman"
    course_run.font.size = Pt(14)

    document.add_paragraph()

    metadata = document.add_paragraph()
    metadata.add_run("Статус черновика: ").bold = True
    metadata.add_run(STATUS_LABELS.get(draft.status, draft.status))

    document.add_paragraph()

    content_heading = document.add_paragraph()
    content_heading_run = content_heading.add_run("Текст черновика")
    content_heading_run.bold = True

    add_multiline_text_to_docx(document, draft.content)

    if draft.feedback:
        document.add_page_break()

        feedback_heading = document.add_paragraph()
        feedback_heading_run = feedback_heading.add_run("Замечания методиста")
        feedback_heading_run.bold = True

        add_multiline_text_to_docx(document, draft.feedback)

    output = BytesIO()
    document.save(output)
    output.seek(0)

    return output