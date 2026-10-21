"""Local Ollama embeddings with validated vectors and an on-disk document cache."""
import json
import math
import os
import sqlite3
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

import httpx

from app.config import PROJECT_DIR


class EmbeddingError(Exception):
    pass


@dataclass(frozen=True)
class EmbeddingSettings:
    model: str
    base_url: str
    timeout: float
    cache_path: Path

    @classmethod
    def from_environment(cls):
        try:
            model = os.getenv("OLLAMA_EMBEDDING_MODEL", "qwen3-embedding:0.6b").strip()
            base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").strip().rstrip("/")
            timeout = float(os.getenv("EMBEDDING_TIMEOUT_SECONDS", "120"))
            cache = Path(os.getenv("COMPETENCY_EMBEDDING_CACHE", str(PROJECT_DIR / ".cache" / "competency_embeddings.sqlite3"))).expanduser()
            if not cache.is_absolute():
                cache = PROJECT_DIR / cache
            if not model or not base.startswith(("http://", "https://")) or not 1 <= timeout <= 600:
                raise ValueError("Invalid embedding settings")
        except (TypeError, ValueError) as error:
            raise EmbeddingError("Проверьте настройки локальной модели поиска.") from error
        return cls(model, base, timeout, cache)


def unit_vector(vector):
    if not isinstance(vector, list) or not 1 <= len(vector) <= 8192:
        raise ValueError("Invalid embedding dimensions")
    if any(isinstance(item, bool) or not isinstance(item, (int, float)) or not math.isfinite(item) for item in vector):
        raise ValueError("Embedding contains non-finite values")
    norm = math.sqrt(sum(float(item) ** 2 for item in vector))
    if not math.isfinite(norm) or norm <= 0:
        raise ValueError("Zero embedding vector")
    return [float(item) / norm for item in vector]


class OllamaEmbeddings:
    def __init__(self, config):
        self.config = config
        self.client = None

    def __enter__(self):
        self.client = httpx.Client(timeout=httpx.Timeout(self.config.timeout, connect=5))
        return self

    def __exit__(self, *args):
        self.client.close()

    def request(self, method, endpoint, **kwargs):
        try:
            response = self.client.request(method, self.config.base_url + endpoint, **kwargs)
            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException as error:
            raise EmbeddingError("Локальная модель не завершила поиск вовремя. Повторите запрос.") from error
        except httpx.ConnectError as error:
            raise EmbeddingError("Не удалось подключиться к Ollama. Запустите локальный сервер модели поиска.") from error
        except httpx.HTTPStatusError as error:
            if error.response.status_code == 404:
                message = "Локальная модель поиска не установлена. Установите модель, указанную в настройках поиска."
            elif error.response.status_code == 400:
                message = "Модель не смогла обработать запрос. Проверьте модель поиска и длину описания дисциплины."
            else:
                message = "Ollama отклонила запрос к локальной модели поиска."
            raise EmbeddingError(message) from error
        except (httpx.HTTPError, ValueError) as error:
            raise EmbeddingError("Не удалось получить корректный ответ локальной модели поиска.") from error

    def model_digest(self):
        payload = self.request("GET", "/api/tags")
        name = self.config.model if ":" in self.config.model else self.config.model + ":latest"
        models = payload.get("models") if isinstance(payload, dict) else None
        if not isinstance(models, list):
            raise EmbeddingError("Ollama вернула некорректный список локальных моделей.")
        for model in models:
            if isinstance(model, dict) and name in {model.get("name"), model.get("model")}:
                digest = model.get("digest")
                if isinstance(digest, str) and digest:
                    return digest
        raise EmbeddingError("Локальная модель поиска не установлена. Установите модель, указанную в настройках поиска.")

    def embed(self, texts):
        data = self.request("POST", "/api/embed", json={
            "model": self.config.model, "input": texts, "truncate": False,
            "keep_alive": "5m", "options": {"num_ctx": 32768},
        })
        try:
            vectors = data["embeddings"]
            if not isinstance(vectors, list) or len(vectors) != len(texts):
                raise ValueError("Embedding count differs from input count")
            result = [unit_vector(vector) for vector in vectors]
            if len({len(vector) for vector in result}) != 1:
                raise ValueError("Inconsistent embedding dimensions")
            return result
        except (KeyError, TypeError, ValueError, OverflowError) as error:
            raise EmbeddingError("Модель поиска вернула некорректные векторы. Повторите запрос или проверьте модель.") from error


class EmbeddingCache:
    def __init__(self, path, namespace):
        self.path, self.namespace = path, namespace
        self.connection = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path, timeout=30)
        self.connection.execute("CREATE TABLE IF NOT EXISTS embeddings (namespace TEXT NOT NULL, text_hash TEXT NOT NULL, vector TEXT NOT NULL, PRIMARY KEY (namespace, text_hash))")
        return self

    def __exit__(self, *args):
        self.connection.close()

    def get(self, text, dimensions):
        row = self.connection.execute("SELECT vector FROM embeddings WHERE namespace=? AND text_hash=?", (self.namespace, sha256(text.encode()).hexdigest())).fetchone()
        if row:
            try:
                vector = unit_vector(json.loads(row[0]))
                if len(vector) == dimensions:
                    return vector
            except (ValueError, TypeError, OverflowError):
                pass
        return None

    def put(self, texts, vectors):
        self.connection.executemany("INSERT OR REPLACE INTO embeddings VALUES (?, ?, ?)", [
            (self.namespace, sha256(text.encode()).hexdigest(), json.dumps(vector, allow_nan=False)) for text, vector in zip(texts, vectors, strict=True)
        ])
        self.connection.commit()
