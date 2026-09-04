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

API_KEY = (
    os.environ.get("OPENAI_API_KEY")
    or os.environ.get("REGOLO_API_KEY")
    or os.environ.get("LLM_API_KEY")
)
HOST = os.environ.get("OPENAI_BASE_URL") or os.environ.get("LLM_HOST") or "https://api.regolo.ai/v1"
MODEL = os.environ.get("LLM_MODEL", "gpt-oss-120b")

CHAT_URL = urljoin(HOST + "/", "chat/completions")

# rate limiting
MAX_RETRIES = int(os.environ.get("LLM_MAX_RETRIES", "3"))
RETRY_DELAY = float(os.environ.get("LLM_RETRY_DELAY", "2.0"))
REQUEST_TIMEOUT = int(os.environ.get("LLM_TIMEOUT", "60"))  # existing, keep for non-streaming calls

# Per-model timeouts now come from profiles.get_profile(model).timeout
# This replaces the old _MODEL_TIMEOUTS dict


def get_model_timeout(model: str | None = None) -> int:
    """Get per-model timeout in seconds. Env override: LLM_TIMEOUT_{MODEL}."""
    from .profiles import get_profile

    model_name = model or MODEL
    profile = get_profile(model_name)

    # Check for explicit env override first (legacy support)
    env_key = f"LLM_TIMEOUT_{model_name.upper().replace('-', '_')}"
    if env_val := os.environ.get(env_key):
        return int(env_val)

    return profile.timeout


# Wall-clock timeouts now come from profiles.get_profile(model).review_timeout
# These are kept for backward compatibility but should use profiles going forward
READ_TIMEOUT = int(os.environ.get("LLM_READ_TIMEOUT", "120"))  # per-read socket timeout
WALL_CLOCK_GLM = 1800  # legacy alias: reasoning-profile review timeout, 30 min
WALL_CLOCK_LONG = 900  # other models, long prompts: 15 min
WALL_CLOCK_DEFAULT = 300  # other models: 5 min
WALL_CLOCK_CATEGORY = 300  # per-category distill: 5 min

# Max tokens now comes from profiles.get_profile(model).max_tokens
# This is kept for backward compatibility
GLM_MAX_TOKENS = 16000  # legacy alias: reasoning-profile max tokens


def headers() -> dict:
    if not API_KEY:
        raise RuntimeError(
            "No API key found. Set REGOLO_API_KEY, OPENAI_API_KEY, or LLM_API_KEY "
            "in your environment or .env file (see .env.example)."
        )
    return {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }


# LLM cache configuration
LLM_CACHE_PATH = os.environ.get("LLM_CACHE_PATH", "data/llm_cache.jsonl")
LLM_CACHE_TTL_HOURS = float(os.environ.get("LLM_CACHE_TTL_HOURS", "24"))
