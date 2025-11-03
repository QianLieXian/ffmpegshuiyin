from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field, validator

from .models import JobStatus, WatermarkType


class WatermarkSettingsIn(BaseModel):
    type: WatermarkType
    text: Optional[str] = Field(None, description="Text content for watermark")
    font_path: Optional[str] = None
    font_size: int = Field(36, ge=8, le=256)
    color: str = Field("white", description="Color in hex or named format")
    image_path: Optional[str] = Field(
        None, description="Path to watermark image (PNG with transparency recommended)"
    )
    opacity: float = Field(1.0, ge=0.0, le=1.0)
    position: Literal[
        "top-left",
        "top-right",
        "bottom-left",
        "bottom-right",
        "center",
    ] = "top-right"
    offset_x: int = Field(20, ge=0, le=4096)
    offset_y: int = Field(20, ge=0, le=4096)

    @validator("text")
    def validate_text(cls, value: Optional[str], values: dict) -> Optional[str]:
        if values.get("type") == WatermarkType.TEXT and not value:
            raise ValueError("Text watermark requires 'text' field")
        return value

    @validator("image_path")
    def validate_image_path(cls, value: Optional[str], values: dict) -> Optional[str]:
        if values.get("type") == WatermarkType.IMAGE and not value:
            raise ValueError("Image watermark requires 'image_path' field")
        return value


class JobCreateResponse(BaseModel):
    job_id: str


class JobListItem(BaseModel):
    id: str
    status: JobStatus
    progress: float
    created_at: float
    started_at: Optional[float]
    finished_at: Optional[float]


class JobDetail(JobListItem):
    watermark: WatermarkSettingsIn
    output_format: str
    output_dir: str
    target_device: Literal["cpu", "intel", "nvidia"]
    metadata: dict
    log: List[str]
    input_files: List[str]


class SettingsResponse(BaseModel):
    max_parallel_jobs: int
    allow_gpu: bool
    default_output_format: str
    ffmpeg_binary: str


class SettingsUpdate(BaseModel):
    max_parallel_jobs: Optional[int]
    allow_gpu: Optional[bool]
    default_output_format: Optional[str]
    ffmpeg_binary: Optional[str]

    @validator("max_parallel_jobs")
    def validate_parallel_jobs(cls, value: Optional[int]) -> Optional[int]:
        if value is not None and value < 1:
            raise ValueError("max_parallel_jobs must be >= 1")
        return value

    @validator("default_output_format")
    def validate_output_format(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not value:
            raise ValueError("default_output_format cannot be empty")
        return value
