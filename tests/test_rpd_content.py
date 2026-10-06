import json

import pytest

from app.services.rpd_content_service import content_prompt, parse_content, render_content, source_context

def test_each_source_gets_input_budget_including_end_of_large_file():
    materials = "[Источник: first.pdf]\n" + "A" * 24000 + "END-FIRST\n\n[Источник: second.pptx]\nMETRIC-SLIDES\n\n[Источник: third.ipynb]\nNOTEBOOK"
    context, names = source_context(materials)
    assert len(context) <= 16000
    assert "END-FIRST" in context
    assert "METRIC-SLIDES" in context
    assert "NOTEBOOK" in context
    assert names == ["first.pdf", "second.pptx", "third.ipynb"]

def test_prompt_requires_teaching_content_without_competency_codes(sample_course):
    prompt, names = content_prompt(sample_course, "Material concepts")
    assert "СФОРМУЛИРУЙ" in prompt
    assert "коды компетенций" in prompt
    assert "Material concepts" in prompt

def test_renderer_preserves_entered_facts_and_has_plain_headings(sample_course, teaching_payload):
    from decimal import Decimal
    sample_course.total_hours = 40
    sample_course.credits = Decimal("4")
    sample_course.assessment_format = "pass"
    teaching_payload["objectives"][0] = "**" + teaching_payload["objectives"][0] + "**"
    content = parse_content(json.dumps(teaching_payload), ["lecture.pdf"])
    result = render_content(sample_course, content, ["lecture.pdf"])
    assert "Академические часы: 40" in result
    assert "Зачетные единицы: 4" in result
    assert "Зачет" in result
    assert "Экзамен" not in result
    assert "**" not in result
    assert "Коды компетенций не назначены" in result
    assert "ОПК-1" not in result
    assert teaching_payload["objectives"][0].replace("**", "") in result
    assert teaching_payload["assessment_tasks"][0]["task"] in result
    assert teaching_payload["assessment_tasks"][0]["expected_result"] in result
    assert "Основание: lecture.pdf" in result

@pytest.mark.parametrize("field", ["objectives", "knowledge", "skills", "assessment_tasks"])
def test_empty_teaching_sections_are_rejected(teaching_payload, field):
    teaching_payload[field] = []
    with pytest.raises(ValueError):
        parse_content(json.dumps(teaching_payload), ["lecture.pdf"])

def test_placeholder_goals_are_rejected(teaching_payload):
    teaching_payload["objectives"][0] = "уточняется преподавателем"
    with pytest.raises(ValueError):
        parse_content(json.dumps(teaching_payload), ["lecture.pdf"])

def test_unknown_source_references_are_rejected(teaching_payload):
    teaching_payload["topics"][0]["source_ids"] = [3]
    with pytest.raises(ValueError):
        parse_content(json.dumps(teaching_payload), ["lecture.pdf"])

def test_generated_administrative_facts_are_rejected(teaching_payload):
    teaching_payload["total_hours"] = 108
    with pytest.raises(ValueError):
        parse_content(json.dumps(teaching_payload), ["lecture.pdf"])


def test_reference_examples_are_separate_and_bounded(tmp_path, monkeypatch, sample_course):
    from docx import Document
    from app.services.rpd_example_service import reference_examples
    document = Document()
    document.add_paragraph("1. Цели освоения дисциплины")
    document.add_paragraph("Познакомить студентов с методами исследования операций.")
    document.add_paragraph("2. Место дисциплины")
    document.add_paragraph("Чужая образовательная программа")
    document.add_paragraph("3. Планируемые результаты")
    document.add_paragraph("ОПК-1. Чужая компетенция")
    document.add_paragraph("Уметь сравнивать алгоритмы решения оптимизационных задач.")
    document.add_paragraph("4. Трудоемкость")
    document.add_paragraph("108 часов")
    document.add_paragraph("5. Содержание дисциплины")
    document.add_paragraph("Линейное программирование и динамическое программирование.")
    document.add_paragraph("6. Литература")
    document.save(tmp_path / "РПД пример.docx")
    monkeypatch.setenv("RPD_EXAMPLES_DIR", str(tmp_path))
    example = reference_examples(str(tmp_path))
    assert "Познакомить студентов" in example
    assert "ОПК-1" not in example
    assert "108 часов" not in example
    assert len(example) <= 5500
    prompt, sources = content_prompt(sample_course, "Учебные данные новой дисциплины")
    assert "ТОЛЬКО примеры стиля" in prompt
    assert "НЕ переноси" in prompt
    assert "Познакомить студентов" in prompt
    assert sources == ["Материалы преподавателя"]


def test_model_cannot_supply_an_administrative_introduction(teaching_payload):
    teaching_payload["summary"] = "Чужая программа 01.04.01 из образца РПД"
    with pytest.raises(ValueError):
        parse_content(json.dumps(teaching_payload), ["lecture.pdf"])


def test_generic_assessment_tasks_without_expected_results_are_rejected(teaching_payload):
    teaching_payload["assessment_tasks"] = ["Оценить качество модели"] * 3
    with pytest.raises(ValueError):
        parse_content(json.dumps(teaching_payload), ["lecture.pdf"])
