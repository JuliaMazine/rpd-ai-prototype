import os

import pytest

from app.services.llm_service import (
    build_rpd_prompt,
    build_template_draft,
    generate_draft_text,
)


class TestBuildTemplateDraft:
    def test_returns_string_with_course_title(self, sample_course):
        result = build_template_draft(sample_course, "material text here")
        assert isinstance(result, str)
        assert sample_course.title in result

    def test_includes_description(self, sample_course):
        result = build_template_draft(sample_course, "material text here")
        assert sample_course.description in result

    def test_includes_materials_text(self, sample_course):
        materials = "This is the course material content."
        result = build_template_draft(sample_course, materials)
        assert materials in result

    def test_truncates_long_materials(self, sample_course):
        long_text = "A" * 5000
        result = build_template_draft(sample_course, long_text)
        assert len(result) > 0
        assert "AAAA" in result

    def test_structure_contains_required_sections(self, sample_course):
        result = build_template_draft(sample_course, "materials")
        sections = [
            "Цели освоения дисциплины",
            "Место дисциплины в структуре ООП",
            "Перечень планируемых результатов",
            "Трудоемкость дисциплины",
            "Содержание дисциплины",
            "Перечень учебной литературы",
            "Материально-техническая база",
            "Оценочные средства",
        ]
        for section in sections:
            assert section in result, f"Missing section: {section}"


class TestBuildRpdPrompt:
    def test_contains_system_instructions(self, sample_course):
        prompt = build_rpd_prompt(sample_course, "materials")
        assert "рабочей программы дисциплины" in prompt.lower()
        assert "русском" in prompt

    def test_includes_course_info(self, sample_course):
        prompt = build_rpd_prompt(sample_course, "materials")
        assert sample_course.title in prompt
        assert sample_course.description in prompt

    def test_truncates_materials_to_16k(self, sample_course):
        long_materials = "B" * 20000
        prompt = build_rpd_prompt(sample_course, long_materials)
        assert len(long_materials) > 16000
        assert "BBBB" in prompt

    def test_structure_outline_present(self, sample_course):
        prompt = build_rpd_prompt(sample_course, "materials")
        sections = [
            "1. Цели освоения дисциплины",
            "2. Место дисциплины в структуре ООП",
            "3. Перечень планируемых результатов",
            "4. Трудоемкость дисциплины",
            "5. Содержание дисциплины",
            "6. Перечень учебной литературы",
            "10. Материально-техническая база",
            "11. Оценочные средства",
        ]
        for section in sections:
            assert section in prompt, f"Missing section in prompt: {section}"


class TestGenerateDraftText:
    def test_fallback_when_no_api_key(self, sample_course, monkeypatch):
        monkeypatch.setenv("VSEGPT_API_KEY", "")
        monkeypatch.setenv("VSEGPT_MODEL", "")
        result = generate_draft_text(sample_course, "materials")
        assert isinstance(result, str)
        assert sample_course.title in result
        assert "VseGPT не использовался" in result

    def test_fallback_when_api_key_missing_but_model_present(self, sample_course, monkeypatch):
        monkeypatch.setenv("VSEGPT_API_KEY", "")
        monkeypatch.setenv("VSEGPT_MODEL", "some-model")
        result = generate_draft_text(sample_course, "materials")
        assert "VseGPT не использовался" in result

    def test_fallback_when_model_missing_but_key_present(self, sample_course, monkeypatch):
        monkeypatch.setenv("VSEGPT_API_KEY", "sk-test")
        monkeypatch.setenv("VSEGPT_MODEL", "")
        result = generate_draft_text(sample_course, "materials")
        assert "VseGPT не использовался" in result

    def test_returns_fallback_on_api_error(self, sample_course, monkeypatch):
        from unittest.mock import Mock
        monkeypatch.setattr("app.services.llm_service.OpenAI", Mock(side_effect=RuntimeError("API failure")))
        monkeypatch.setenv("VSEGPT_API_KEY", "sk-test-key")
        monkeypatch.setenv("VSEGPT_MODEL", "test-model")
        result = generate_draft_text(sample_course, "course materials text")
        assert "VseGPT" in result or "ошибка" in result
        assert sample_course.title in result

    def test_template_draft_contains_materials_section(self, sample_course):
        materials = "Machine learning basics"
        result = build_template_draft(sample_course, materials)
        assert "Материалы, использованные при генерации черновика" in result
        assert materials in result
