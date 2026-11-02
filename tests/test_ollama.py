from unittest.mock import Mock, patch
import json

import httpx
import pytest

from app.config import GenerationSettings
from app.services.llm_service import generate_draft_text

@pytest.fixture
def local_settings(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_MODEL", "qwen3:14b")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434/")
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "600")
    monkeypatch.setenv("LLM_MAX_TOKENS", "4500")
    monkeypatch.setenv("OLLAMA_CONTEXT_LENGTH", "16384")
    monkeypatch.setenv("OLLAMA_KEEP_ALIVE_SECONDS", "900")
    return GenerationSettings.from_environment()

def test_local_provider_needs_no_api_key(local_settings):
    assert local_settings.api_key == ""
    assert local_settings.base_url == "http://localhost:11434"
    assert local_settings.timeout == 600

def test_ollama_receives_russian_prompt_and_returns_generated_text(local_settings, sample_course, teaching_payload, teaching_sources):
    response = Mock()
    response.json.return_value = {"message": {"content": json.dumps(teaching_payload, ensure_ascii=False)}, "done_reason": "stop"}
    with patch("app.services.ollama_service.httpx.Client") as client, patch("app.services.llm_service.OpenAI") as paid_client:
        client.return_value.__enter__.return_value.post.return_value = response
        result = generate_draft_text(sample_course, teaching_sources.full_text)
        assert teaching_payload["objectives"][0].lower().rstrip(".") in result.lower()
        assert "1. Цели освоения дисциплины" in result
        paid_client.assert_not_called()
        call = client.return_value.__enter__.return_value.post.call_args
        assert call.args[0] == "http://localhost:11434/api/chat"
        payload = call.kwargs["json"]
        assert payload["model"] == "qwen3:14b"
        assert payload["stream"] is False
        assert "objectives" in payload["format"]["properties"]
        assert payload["think"] is False
        assert payload["keep_alive"] == 900
        assert payload["messages"][-1]["content"].endswith("/no_think")
        assert payload["options"]["num_ctx"] == 16384
        assert payload["options"]["num_predict"] == 4500
        assert "русском языке" in payload["messages"][0]["content"]
        assert sample_course.title in payload["messages"][1]["content"]
        assert "Материалы преподавателя" in payload["messages"][1]["content"]

@pytest.mark.parametrize("error,reason", [
    (httpx.ConnectError("connection refused"), "не удалось подключиться"),
    (httpx.ReadTimeout("timeout"), "не завершила генерацию"),
    (ValueError("invalid JSON"), "генерация через Ollama не удалась"),
])
def test_ollama_failures_return_marked_template(local_settings, sample_course, error, reason):
    with patch("app.services.llm_service.ollama_service.generate", side_effect=error), patch("app.services.llm_service.OpenAI") as paid_client:
        result = generate_draft_text(sample_course, "Материалы")
        assert sample_course.title in result
        assert reason in result
        assert "шаблонный черновик" in result
        paid_client.assert_not_called()

def test_missing_model_returns_actionable_fallback(local_settings, sample_course):
    request = httpx.Request("POST", "http://localhost:11434/api/chat")
    error = httpx.HTTPStatusError("missing model", request=request, response=httpx.Response(404, request=request))
    with patch("app.services.llm_service.ollama_service.generate", side_effect=error):
        assert "локальная модель Ollama не найдена" in generate_draft_text(sample_course, "Материалы")

def test_empty_response_returns_fallback(local_settings, sample_course):
    with patch("app.services.llm_service.ollama_service.generate", return_value=("", False)):
        assert "Ollama вернул пустой ответ" in generate_draft_text(sample_course, "Материалы")

def test_output_limit_is_visible(local_settings, sample_course):
    with patch("app.services.llm_service.ollama_service.generate", return_value=("Неполный ответ", True)):
        result = generate_draft_text(sample_course, "Материалы")
        assert "шаблонный черновик" in result
        assert "Неполный ответ" not in result
        assert "достигнут лимит длины ответа" in result

def test_template_provider_never_calls_a_model(monkeypatch, sample_course):
    monkeypatch.setenv("LLM_PROVIDER", "template")
    with patch("app.services.llm_service.ollama_service.generate") as local, patch("app.services.llm_service.OpenAI") as paid:
        assert "генерация ИИ отключена" in generate_draft_text(sample_course, "Материалы")
        local.assert_not_called()
        paid.assert_not_called()

@pytest.mark.parametrize("name,value", [("LLM_PROVIDER", "invalid"), ("LLM_TIMEOUT_SECONDS", "NaN"), ("LLM_MAX_TOKENS", "-1"), ("OLLAMA_BASE_URL", "invalid"), ("OLLAMA_CONTEXT_LENGTH", "0"), ("OLLAMA_KEEP_ALIVE_SECONDS", "-1"), ("OLLAMA_KEEP_ALIVE_SECONDS", "3601")])
def test_bad_configuration_falls_back(local_settings, monkeypatch, sample_course, name, value):
    monkeypatch.setenv(name, value)
    assert "ошибка настройки генерации" in generate_draft_text(sample_course, "Материалы")

def test_empty_local_model_never_calls_server(local_settings, monkeypatch, sample_course):
    monkeypatch.setenv("OLLAMA_MODEL", "")
    with patch("app.services.llm_service.ollama_service.generate") as local:
        assert "локальная модель не выбрана" in generate_draft_text(sample_course, "Материалы")
        local.assert_not_called()


def test_usage_metrics_do_not_capture_response_content(local_settings):
    from app.services.ollama_service import generate
    response = Mock()
    response.json.return_value = {
        "message": {"content": "Готовый ответ"}, "done_reason": "stop",
        "total_duration": 1000000000, "load_duration": 0,
        "eval_count": 120, "eval_duration": -1,
        "prompt_eval_count": True, "prompt_eval_duration": "invalid",
        "unrelated": "not performance data",
    }
    metrics = {}
    with patch("app.services.ollama_service.httpx.Client") as client:
        client.return_value.__enter__.return_value.post.return_value = response
        assert generate(local_settings, [], metrics=metrics) == ("Готовый ответ", False)
    assert metrics == {"total_duration": 1000000000, "load_duration": 0, "eval_count": 120}


def test_each_correction_attempt_keeps_its_own_usage(local_settings, sample_course, teaching_payload, teaching_sources):
    import copy
    invalid = copy.deepcopy(teaching_payload)
    invalid["assessment_tasks"][0]["topic_index"] = 6
    responses = iter([invalid, teaching_payload])

    def generate(config, messages, response_schema, *, metrics):
        value = next(responses)
        metrics["eval_count"] = 100 if value is invalid else 200
        return json.dumps(value), False

    metadata = {}
    with patch("app.services.llm_service.ollama_service.generate", side_effect=generate):
        generate_draft_text(sample_course, teaching_sources.full_text, metadata)
    assert metadata["status"] == "validated"
    assert metadata["generation"] == {
        "provider": "ollama", "model": "qwen3:14b",
        "attempts": [{"eval_count": 100}, {"eval_count": 200}],
    }


@pytest.mark.parametrize("content,expected", [
    ("<think>Planning text</think>\nГотовый документ", "Готовый документ"),
    ("Planning without opening tag</think>\nГотовый документ", "Готовый документ"),
    ("<think>Unfinished planning", ""),
    ("  Готовый документ  ", "Готовый документ"),
])
def test_only_final_answer_is_used(content, expected):
    from app.services.ollama_service import final_answer
    assert final_answer(content) == expected


def test_planning_only_response_uses_template(local_settings, sample_course):
    response = Mock()
    response.json.return_value = {"message": {"content": "<think>Planning without final answer"}, "done_reason": "length"}
    with patch("app.services.ollama_service.httpx.Client") as client:
        client.return_value.__enter__.return_value.post.return_value = response
        result = generate_draft_text(sample_course, "Материалы")
        assert "шаблонный черновик" in result
        assert "Planning" not in result


def test_invalid_topic_reference_is_retried_once(local_settings, sample_course, teaching_payload, teaching_sources):
    import copy
    invalid = copy.deepcopy(teaching_payload)
    invalid["assessment_tasks"][0]["topic_index"] = 6
    metadata = {}
    with patch("app.services.llm_service.ollama_service.generate", side_effect=[(json.dumps(invalid), False), (json.dumps(teaching_payload), False)]) as generate:
        result = generate_draft_text(sample_course, teaching_sources.full_text, metadata=metadata)
        assert generate.call_count == 2
        assert metadata["status"] == "validated"
        assert metadata["attempts"] == 2
        assert "шаблонный черновик" not in result
        assert "Исправь JSON" in generate.call_args.args[1][-1]["content"]


@pytest.mark.parametrize("full_response", [False, True])
def test_task_only_correction_preserves_other_sections(local_settings, sample_course, teaching_payload, teaching_sources, full_response):
    import copy
    invalid = copy.deepcopy(teaching_payload)
    invalid["assessment_tasks"][0]["topic_index"] = 6
    corrected = {"assessment_tasks": teaching_payload["assessment_tasks"]}
    if full_response:
        corrected = copy.deepcopy(teaching_payload)
        corrected["objectives"] = ["Посторонняя цель, которой не было в исходном ответе."] * 3
    metadata = {}
    with patch("app.services.llm_service.ollama_service.generate", side_effect=[(json.dumps(invalid), False), (json.dumps(corrected), False)]) as generate:
        result = generate_draft_text(sample_course, teaching_sources.full_text, metadata)
    assert metadata["status"] == "validated"
    assert metadata["teaching_content"]["objectives"] == invalid["objectives"]
    assert "Посторонняя цель" not in result
    schema = generate.call_args.kwargs["response_schema"]
    assert set(schema["properties"]) == {"assessment_tasks"}
    assert schema["required"] == ["assessment_tasks"]


def test_unrelated_errors_require_a_full_correction(local_settings, sample_course, teaching_payload, teaching_sources):
    import copy
    invalid = copy.deepcopy(teaching_payload)
    invalid["objectives"] = []
    metadata = {}
    with patch("app.services.llm_service.ollama_service.generate", side_effect=[(json.dumps(invalid), False), (json.dumps(teaching_payload), False)]) as generate:
        generate_draft_text(sample_course, teaching_sources.full_text, metadata)
    assert metadata["status"] == "validated"
    assert "objectives" in generate.call_args.kwargs["response_schema"]["properties"]


def test_task_correction_cannot_add_administrative_fields(local_settings, sample_course, teaching_payload, teaching_sources):
    import copy
    invalid = copy.deepcopy(teaching_payload)
    invalid["assessment_tasks"][0]["topic_index"] = 6
    corrected = {"assessment_tasks": teaching_payload["assessment_tasks"], "total_hours": 999}
    metadata = {}
    with patch("app.services.llm_service.ollama_service.generate", side_effect=[(json.dumps(invalid), False), (json.dumps(corrected), False)]):
        generate_draft_text(sample_course, teaching_sources.full_text, metadata)
    assert metadata["status"] == "template"

def test_repeated_invalid_evidence_is_never_saved_as_generated_content(local_settings, sample_course, teaching_payload, teaching_sources):
    teaching_payload["topics"][0]["claims"][0]["evidence"]["excerpt_id"] = "FAKE-ID"
    metadata = {}
    with patch("app.services.llm_service.ollama_service.generate", return_value=(json.dumps(teaching_payload), False)) as generate:
        result = generate_draft_text(sample_course, teaching_sources.full_text, metadata=metadata)
        assert generate.call_count == 2
        assert metadata["status"] == "template"
        assert metadata["evidence"] == []
        assert "Выдуманный факт" not in result
        assert "шаблонный черновик" in result
