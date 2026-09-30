"""Environment configuration and paths, independent of the launch directory."""
import os
from dataclasses import dataclass, field
from pathlib import Path
from secrets import token_urlsafe

from dotenv import load_dotenv

APP_DIR = Path(__file__).resolve().parent
PROJECT_DIR = APP_DIR.parent
load_dotenv(PROJECT_DIR / '.env')

@dataclass(frozen=True)
class Settings:
    database_url: str = field(default_factory=lambda: os.getenv('DATABASE_URL', ''))
    session_secret: str = field(default_factory=lambda: os.getenv('SESSION_SECRET') or token_urlsafe(32))
    seed_demo: bool = field(default_factory=lambda: os.getenv('SEED_DEMO_DATA', 'false').lower() == 'true')
    secure_cookies: bool = field(default_factory=lambda: os.getenv('SECURE_COOKIES', 'false').lower() == 'true')
    upload_dir: Path = field(default_factory=lambda: Path(os.getenv('UPLOAD_DIR', str(PROJECT_DIR / 'uploads'))).resolve())
    max_upload_bytes: int = 5 * 1024 * 1024

settings = Settings()
