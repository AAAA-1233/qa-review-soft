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
CORS_ORIGINS = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "http://127.0.0.1:5173,http://127.0.0.1:4173,http://localhost:5173,http://localhost:4173").split(",") if origin.strip()]
ALLOW_SERVER_PATH_IMPORT = _bool_env("ALLOW_SERVER_PATH_IMPORT", False)
SEED_SAMPLE_DATA = _bool_env("SEED_SAMPLE_DATA", True)
