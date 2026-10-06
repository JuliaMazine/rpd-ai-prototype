"""Environment configuration and paths, independent of the launch directory."""
import os
from dataclasses import dataclass, field
from pathlib import Path
from secrets import token_urlsafe

from dotenv import load_dotenv

APP_DIR = Path(__file__).resolve().parent
PROJECT_DIR = APP_DIR.parent
load_dotenv(PROJECT_DIR / '.env')

def upload_limit_bytes():
    limit_mb = int(os.getenv("MAX_UPLOAD_MB", "25"))
    if not 1 <= limit_mb <= 100:
        raise ValueError("MAX_UPLOAD_MB must be an integer between 1 and 100")
    return limit_mb * 1024 * 1024

@dataclass(frozen=True)
class Settings:
    database_url: str = field(default_factory=lambda: os.getenv('DATABASE_URL', ''))
    session_secret: str = field(default_factory=lambda: os.getenv('SESSION_SECRET') or token_urlsafe(32))
    seed_demo: bool = field(default_factory=lambda: os.getenv('SEED_DEMO_DATA', 'false').lower() == 'true')
    secure_cookies: bool = field(default_factory=lambda: os.getenv('SECURE_COOKIES', 'false').lower() == 'true')
    upload_dir: Path = field(default_factory=lambda: Path(os.getenv('UPLOAD_DIR', str(PROJECT_DIR / 'uploads'))).resolve())
    max_upload_bytes: int = field(default_factory=upload_limit_bytes)

settings = Settings()


@dataclass(frozen=True)
class GenerationSettings:
    provider: str
    model: str
    base_url: str
    api_key: str = field(repr=False)
    timeout: float
    max_tokens: int
    context_length: int

    @classmethod
    def from_environment(cls):
        # Retain VseGPT as the default for existing installations.
        provider = os.getenv("LLM_PROVIDER", "vsegpt").strip().lower()
        if provider not in {"ollama", "vsegpt", "template"}:
            raise ValueError("LLM_PROVIDER must be ollama, vsegpt or template")
        timeout = float(os.getenv("LLM_TIMEOUT_SECONDS", "600" if provider == "ollama" else "90"))
        max_tokens = int(os.getenv("LLM_MAX_TOKENS", "4500"))
        context_length = int(os.getenv("OLLAMA_CONTEXT_LENGTH", "16384"))
        if not 1 <= timeout <= 3600 or not 1 <= max_tokens <= 32768 or not 512 <= context_length <= 131072:
            raise ValueError("Generation limits are out of range")
        if provider == "ollama":
            model = os.getenv("OLLAMA_MODEL", "").strip()
            base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").strip().rstrip("/")
            api_key = ""
        else:
            model = os.getenv("VSEGPT_MODEL", "").strip()
            base_url = os.getenv("VSEGPT_BASE_URL", "https://api.vsegpt.ru/v1").strip().rstrip("/")
            api_key = os.getenv("VSEGPT_API_KEY", "").strip()
        if provider != "template" and not base_url.startswith(("http://", "https://")):
            raise ValueError("Generation base URL must use HTTP or HTTPS")
        return cls(provider, model, base_url, api_key, timeout, max_tokens, context_length)
