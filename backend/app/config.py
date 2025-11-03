from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic import BaseSettings, Field, validator


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    app_name: str = "FFmpeg Shuiyin"
    environment: Literal["development", "production", "testing"] = Field(
        "development", env="FFMPEGSHUIYIN_ENV"
    )
    api_prefix: str = "/api"
    storage_root: Path = Field(Path(os.environ.get("FFMPEGSHUIYIN_STORAGE", "storage")))
    upload_dir: str = "uploads"
    output_dir: str = "output"
    temp_dir: str = "tmp"
    default_output_format: str = "mp4"
    max_parallel_jobs: int = Field(2, env="FFMPEGSHUIYIN_MAX_PARALLEL_JOBS")
    ffmpeg_binary: str = Field("ffmpeg", env="FFMPEG_BINARY")
    allow_gpu: bool = Field(False, env="FFMPEGSHUIYIN_ALLOW_GPU")

    class Config:
        env_file = ".env"
        env_prefix = "FFMPEGSHUIYIN_"

    @validator("max_parallel_jobs")
    def _validate_parallel_jobs(cls, value: int) -> int:
        if value < 1:
            raise ValueError("max_parallel_jobs must be at least 1")
        return value

    @property
    def upload_path(self) -> Path:
        return self.storage_root / self.upload_dir

    @property
    def output_path(self) -> Path:
        return self.storage_root / self.output_dir

    @property
    def temp_path(self) -> Path:
        return self.storage_root / self.temp_dir


settings = Settings()

for path in (settings.upload_path, settings.output_path, settings.temp_path):
    path.mkdir(parents=True, exist_ok=True)
