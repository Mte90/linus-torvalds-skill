"""
config.py — single source of truth for LLM connection settings.

All three values (host, model, key) are configurable via environment
variables. A .env file is loaded if present; env vars take precedence.
"""

import os
from pathlib import Path
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parent.parent.parent


def _load_dotenv():
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip()
        if key and key not in os.environ:
            os.environ[key] = val


_load_dotenv()

API_KEY = os.environ.get("LLM_API_KEY", "")
HOST = os.environ.get("LLM_HOST", "https://api.regolo.ai/v1")
MODEL = os.environ.get("LLM_MODEL", "gpt-oss-120b")

CHAT_URL = urljoin(HOST + "/", "chat/completions")

# rate limiting
MAX_RETRIES = int(os.environ.get("LLM_MAX_RETRIES", "3"))
RETRY_DELAY = float(os.environ.get("LLM_RETRY_DELAY", "2.0"))
REQUEST_TIMEOUT = int(os.environ.get("LLM_TIMEOUT", "60"))


def headers() -> dict:
    return {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
