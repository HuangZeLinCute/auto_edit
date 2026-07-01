import os
import sys
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None


def _resolve_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


BASE_DIR = _resolve_base_dir()
if load_dotenv:
    load_dotenv(BASE_DIR / ".env")


class Settings:
    app_env: str = "production"
    app_port: int = 8000
    log_level: str = "info"

    database_url: str = ""
    redis_url: str = ""

    storage_type: str = "local"
    storage_path: str = "./storage"

    llm_provider: str = os.environ.get("LLM_PROVIDER", "deepseek")
    llm_model: str = os.environ.get("LLM_MODEL", "deepseek-chat")
    llm_api_key: str = os.environ.get("LLM_API_KEY", "")
    llm_base_url: str = os.environ.get("LLM_BASE_URL", "https://api.deepseek.com")

    whisper_model_size: str = os.environ.get("WHISPER_MODEL_SIZE", "tiny")
    whisper_device: str = os.environ.get("WHISPER_DEVICE", "cpu")
    whisper_compute_type: str = os.environ.get("WHISPER_COMPUTE_TYPE", "int8")

    image_gen_provider: str = ""
    comfyui_url: str = "http://localhost:8188"

    celery_broker_url: str = ""
    celery_result_backend: str = ""


_settings: Optional[Settings] = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
STORAGE_DIR = BASE_DIR / "storage"
UPLOADS_DIR = STORAGE_DIR / "uploads"
OUTPUTS_DIR = STORAGE_DIR / "outputs"
TEMP_DIR = STORAGE_DIR / "temp"
CONFIGS_DIR = BASE_DIR / "configs"
ASSETS_DIR = BASE_DIR / "assets"
PROMPTS_DIR = BASE_DIR / "app" / "prompts"

for d in [UPLOADS_DIR, OUTPUTS_DIR, TEMP_DIR]:
    os.makedirs(d, exist_ok=True)
