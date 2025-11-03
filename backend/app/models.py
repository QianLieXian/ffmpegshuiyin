from __future__ import annotations

import enum
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Literal, Optional


class WatermarkType(str, enum.Enum):
    TEXT = "text"
    IMAGE = "image"


class JobStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class WatermarkSettings:
    type: WatermarkType
    text: Optional[str] = None
    font_path: Optional[str] = None
    font_size: int = 36
    color: str = "white"
    image_path: Optional[Path] = None
    opacity: float = 1.0
    position: Literal[
        "top-left",
        "top-right",
        "bottom-left",
        "bottom-right",
        "center",
    ] = "top-right"
    offset_x: int = 20
    offset_y: int = 20


@dataclass
class Job:
    input_files: List[Path]
    watermark: WatermarkSettings
    output_format: str = "mp4"
    output_dir: Path = Path("output")
    target_device: Literal["cpu", "intel", "nvidia"] = "cpu"
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    status: JobStatus = JobStatus.QUEUED
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    progress: float = 0.0
    log: List[str] = field(default_factory=list)
    metadata: Dict[str, str] = field(default_factory=dict)

    def append_log(self, message: str) -> None:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        entry = f"[{timestamp}] {message}"
        self.log.append(entry)

    def to_dict(self) -> Dict[str, object]:
        return {
            "id": self.id,
            "status": self.status.value,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "progress": self.progress,
            "watermark": {
                "type": self.watermark.type.value,
                "text": self.watermark.text,
                "font_size": self.watermark.font_size,
                "color": self.watermark.color,
                "opacity": self.watermark.opacity,
                "position": self.watermark.position,
                "offset_x": self.watermark.offset_x,
                "offset_y": self.watermark.offset_y,
                "font_path": self.watermark.font_path,
                "image_path": str(self.watermark.image_path)
                if self.watermark.image_path
                else None,
            },
            "output_format": self.output_format,
            "output_dir": str(self.output_dir),
            "target_device": self.target_device,
            "metadata": self.metadata,
            "log": self.log,
        }
