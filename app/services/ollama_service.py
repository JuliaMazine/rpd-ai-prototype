"""Native Ollama chat transport: local generation needs no API key."""
import httpx

from app.config import GenerationSettings

def generate(config: GenerationSettings, messages: list[dict[str, str]]) -> tuple[str, bool]:
    with httpx.Client(timeout=httpx.Timeout(config.timeout, connect=5.0)) as client:
        response = client.post(
            f"{config.base_url}/api/chat",
            json={
                "model": config.model,
                "messages": messages,
                "stream": False,
                "think": False,
                "options": {
                    "temperature": 0.15,
                    "num_predict": config.max_tokens,
                    "num_ctx": config.context_length,
                },
            },
        )
        response.raise_for_status()
        data = response.json()
    if not isinstance(data, dict) or data.get("error"):
        raise ValueError("Invalid Ollama response")
    message = data.get("message")
    if not isinstance(message, dict) or not isinstance(message.get("content"), str):
        raise ValueError("Ollama response has no text content")
    return message["content"].strip(), data.get("done_reason") == "length"
