from __future__ import annotations

import os
from pathlib import Path


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.getenv("QA_DATA_DIR", str(BASE_DIR / "data"))).resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR / 'review.db'}")
CORS_ORIGINS = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "http://127.0.0.1:5173,http://127.0.0.1:4173,http://localhost:5173,http://localhost:4173,http://127.0.0.1:4183,http://localhost:4183").split(",") if origin.strip()]
ALLOW_SERVER_PATH_IMPORT = _bool_env("ALLOW_SERVER_PATH_IMPORT", False)
SEED_SAMPLE_DATA = _bool_env("SEED_SAMPLE_DATA", True)

AUTH_SECRET = os.getenv("AUTH_SECRET", "dev-change-this-auth-secret")
AUTH_TOKEN_EXPIRE_HOURS = int(os.getenv("AUTH_TOKEN_EXPIRE_HOURS", "168"))
AUTH_CODE_EXPIRE_MINUTES = int(os.getenv("AUTH_CODE_EXPIRE_MINUTES", "10"))
AUTH_CODE_DEV_MODE = _bool_env("AUTH_CODE_DEV_MODE", False)

EMAIL_FROM = os.getenv("EMAIL_FROM", "")
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_TLS = _bool_env("SMTP_TLS", True)
