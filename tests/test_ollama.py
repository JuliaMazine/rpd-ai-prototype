from unittest.mock import Mock, patch

import httpx
import pytest

from app.config import GenerationSettings
from app.services.llm_service import generate_draft_text

@pytest.fixture
def local_settings(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_MODEL", "qwen3:4b")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434/")
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "600")
    monkeypatch.setenv("LLM_MAX_TOKENS", "4500")
    monkeypatch.setenv("OLLAMA_CONTEXT_LENGTH", "16384")
    return GenerationSettings.from_environment()

def test_local_provider_needs_no_api_key(local_settings):
    assert local_settings.api_key == ""
    assert local_settings.base_url == "http://localhost:11434"
    assert local_settings.timeout == 600

def test_ollama_receives_russian_prompt_and_returns_generated_text(local_settings, sample_course):
    response = Mock()
    response.json.return_value = {"message": {"content": "  Черновик от локальной модели  "}, "done_reason": "stop"}
    with patch("app.services.ollama_service.httpx.Client") as client, patch("app.services.llm_service.OpenAI") as paid_client:
        client.return_value.__enter__.return_value.post.return_value = response
        result = generate_draft_text(sample_course, "Материалы преподавателя")
        assert result == "Черновик от локальной модели"
        paid_client.assert_not_called()
        call = client.return_value.__enter__.return_value.post.call_args
        assert call.args[0] == "http://localhost:11434/api/chat"
        payload = call.kwargs["json"]
        assert payload["model"] == "qwen3:4b"
        assert payload["stream"] is False
        assert payload["think"] is False
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
        assert result.startswith("Неполный ответ")
        assert "достигнут лимит длины ответа" in result

def test_template_provider_never_calls_a_model(monkeypatch, sample_course):
    monkeypatch.setenv("LLM_PROVIDER", "template")
    with patch("app.services.llm_service.ollama_service.generate") as local, patch("app.services.llm_service.OpenAI") as paid:
        assert "генерация ИИ отключена" in generate_draft_text(sample_course, "Материалы")
        local.assert_not_called()
        paid.assert_not_called()

@pytest.mark.parametrize("name,value", [("LLM_PROVIDER", "invalid"), ("LLM_TIMEOUT_SECONDS", "NaN"), ("LLM_MAX_TOKENS", "-1"), ("OLLAMA_BASE_URL", "invalid"), ("OLLAMA_CONTEXT_LENGTH", "0")])
def test_bad_configuration_falls_back(local_settings, monkeypatch, sample_course, name, value):
    monkeypatch.setenv(name, value)
    assert "ошибка настройки генерации" in generate_draft_text(sample_course, "Материалы")

def test_empty_local_model_never_calls_server(local_settings, monkeypatch, sample_course):
    monkeypatch.setenv("OLLAMA_MODEL", "")
    with patch("app.services.llm_service.ollama_service.generate") as local:
        assert "локальная модель не выбрана" in generate_draft_text(sample_course, "Материалы")
        local.assert_not_called()
