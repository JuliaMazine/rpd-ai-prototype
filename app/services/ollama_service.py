"""Native Ollama chat transport: local generation needs no API key."""
import httpx

from app.config import GenerationSettings

def generate(config: GenerationSettings, messages: list[dict[str, str]], response_schema: dict | None = None) -> tuple[str, bool]:
    messages = [message.copy() for message in messages]
    # Qwen3 also supports this prompt switch on older Ollama/model templates.
    if config.model.lower().split(":", 1)[0] == "qwen3":
        for message in reversed(messages):
            if message["role"] == "user":
                message["content"] += "\n/no_think"
                break
    with httpx.Client(timeout=httpx.Timeout(config.timeout, connect=5.0)) as client:
        response = client.post(
            f"{config.base_url}/api/chat",
            json={
                **({"format": response_schema} if response_schema else {}),
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
    return final_answer(message["content"]), data.get("done_reason") == "length"


def final_answer(content: str) -> str:
    """Some model templates emit a closing reasoning tag without an opening tag."""
    if "</think>" in content:
        content = content.rsplit("</think>", 1)[1]
    if "<think>" in content:
        # No finished answer yet; never save an incomplete reasoning block.
        content = content.split("<think>", 1)[0]
    return content.strip()
