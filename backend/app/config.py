"""Application configuration — pydantic-settings, loaded from .env."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Server
    backend_host: str = "0.0.0.0"
    backend_port: int = 8001

    # Storage
    data_dir: Path = Path("./data")
    upload_dir: Path = Path("./uploads")
    database_url: str = "sqlite:///./data/isgec.db"
    max_upload_mb: int = 100

    # CORS — comma-separated list
    cors_origins: str = "http://localhost:3001,http://127.0.0.1:3001"

    # LLM
    llm_provider: str = Field(default="gemini")  # 'gemini' | 'ollama'
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    gemini_timeout_sec: int = 20

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:14b"

    # Phase 1 tuning
    # Distance threshold (mm) for matching nearest text label to geometry
    label_match_radius_mm: float = 800.0
    # Fuzzy similarity threshold (Jaccard on 3-grams)
    fuzzy_match_threshold: float = 0.55

    # DWG → DXF conversion (libredwg)
    # "auto" resolves the binary from $LIBREDWG_BIN or known install roots.
    libredwg_bin: str = "auto"
    # Backstop on INSERT expansion to avoid pathological drawings blowing up
    # the canvas. Real DWG files in this project emit 15-25k primitives from
    # INSERT expansion; 50k is a generous safety margin.
    max_insert_expansion: int = 50_000

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def upload_dir_abs(self) -> Path:
        p = self.upload_dir if self.upload_dir.is_absolute() else self.data_dir / self.upload_dir
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
