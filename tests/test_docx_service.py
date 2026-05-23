from io import BytesIO

from docx import Document

from app.services.docx_service import (
    add_multiline_text_to_docx,
    build_draft_docx,
    clean_filename,
    encode_docx_filename,
)


class TestCleanFilename:
    def test_keeps_alphanumeric_and_safe_chars(self):
        result = clean_filename("Hello World_1-2.docx")
        assert result == "Hello World_1-2.docx"

    def test_removes_unsafe_chars(self):
        result = clean_filename("hello<world>:test?.docx")
        assert result == "helloworldtest.docx"

    def test_appends_docx_extension(self):
        result = clean_filename("mydraft")
        assert result.endswith(".docx")

    def test_returns_default_for_empty_name(self):
        result = clean_filename("   ")
        assert result == "draft.docx"

    def test_truncates_long_names(self):
        long_name = "a" * 200 + ".docx"
        result = clean_filename(long_name)
        assert len(result) <= 90


class TestEncodeDocxFilename:
    def test_encodes_cjk_characters(self):
        result = encode_docx_filename("черновик.docx")
        assert "%D1%87" in result
        assert result.endswith(".docx")

    def test_encodes_spaces(self):
        result = encode_docx_filename("draft version 1.docx")
        assert "draft%20version%201.docx" in result

    def test_ascii_filename_stays_same(self):
        result = encode_docx_filename("simple.docx")
        assert result == "simple.docx"


class TestAddMultilineTextToDocx:
    def test_adds_empty_lines_as_paragraphs(self):
        doc = Document()
        add_multiline_text_to_docx(doc, "\n\n")
        assert len(doc.paragraphs) > 1

    def test_bolds_uppercase_short_lines(self):
        doc = Document()
        add_multiline_text_to_docx(doc, "РАБОЧАЯ ПРОГРАММА")
        paragraph = doc.paragraphs[0]
        assert paragraph.runs[0].bold is True

    def test_does_not_bold_long_uppercase_lines(self):
        doc = Document()
        long_text = "A" * 100
        add_multiline_text_to_docx(doc, long_text)
        paragraph = doc.paragraphs[0]
        bold = paragraph.runs[0].bold if paragraph.runs else False
        assert bold is not True

    def test_bolds_numbered_sections(self):
        doc = Document()
        add_multiline_text_to_docx(doc, "1. Цели освоения дисциплины")
        paragraph = doc.paragraphs[0]
        assert paragraph.runs[0].bold is True

    def test_bolds_subsection_numbering(self):
        doc = Document()
        add_multiline_text_to_docx(doc, "11.3 Типовые контрольные задания")
        paragraph = doc.paragraphs[0]
        assert paragraph.runs[0].bold is True

    def test_uses_bullet_style_for_list_items(self):
        doc = Document()
        add_multiline_text_to_docx(doc, "• пункт 1")
        paragraph = doc.paragraphs[0]
        assert paragraph.style.name == "List Bullet"

    def test_dash_bullet_uses_list_style(self):
        doc = Document()
        add_multiline_text_to_docx(doc, "- пункт")
        paragraph = doc.paragraphs[0]
        assert paragraph.style.name == "List Bullet"

    def test_regular_text_adds_normal_paragraph(self):
        doc = Document()
        add_multiline_text_to_docx(doc, "Обычный текст параграфа.")
        paragraph = doc.paragraphs[0]
        assert not paragraph.runs or not paragraph.runs[0].bold


class TestBuildDraftDocx:
    def test_returns_bytesio(self, sample_draft):
        result = build_draft_docx(sample_draft)
        assert isinstance(result, BytesIO)
        assert result.getvalue()[:2] == b"PK"

    def test_contains_draft_title_in_document(self, sample_draft):
        result = build_draft_docx(sample_draft)
        doc = Document(result)
        texts = [p.text for p in doc.paragraphs]
        assert "РАБОЧАЯ ПРОГРАММА ДИСЦИПЛИНЫ" in texts

    def test_contains_course_title(self, sample_draft):
        result = build_draft_docx(sample_draft)
        doc = Document(result)
        texts = [p.text for p in doc.paragraphs]
        assert "Test Course" in texts

    def test_contains_draft_status(self, sample_draft):
        result = build_draft_docx(sample_draft)
        doc = Document(result)
        texts = [p.text for p in doc.paragraphs]
        assert any("Статус черновика" in text for text in texts)

    def test_includes_draft_content(self, sample_draft):
        result = build_draft_docx(sample_draft)
        doc = Document(result)
        texts = [p.text for p in doc.paragraphs]
        assert any("Цели освоения дисциплины" in text for text in texts)

    def test_includes_feedback_section_when_present(self, sample_draft):
        sample_draft.feedback = "Необходимо исправить раздел 2."
        result = build_draft_docx(sample_draft)
        doc = Document(result)
        texts = [p.text for p in doc.paragraphs]
        assert any("Замечания методиста" in text for text in texts)
        assert any("Необходимо исправить" in text for text in texts)

    def test_no_feedback_section_when_feedback_is_none(self, sample_draft):
        result = build_draft_docx(sample_draft)
        doc = Document(result)
        texts = [p.text for p in doc.paragraphs]
        feedback_headings = [t for t in texts if "Замечания методиста" in t]
        assert len(feedback_headings) == 0
