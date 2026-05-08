from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_title: str = os.getenv("APP_TITLE", "Система знаний команды")
    api_host: str = os.getenv("API_HOST", "127.0.0.1")
    api_port: int = int(os.getenv("API_PORT", "8000"))
    frontend_origin_localhost: str = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
    frontend_origin_loopback: str = os.getenv("FRONTEND_ORIGIN_LOOPBACK", "http://127.0.0.1:5173")


settings = Settings()

