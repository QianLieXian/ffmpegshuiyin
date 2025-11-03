from __future__ import annotations

import uuid
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .ffmpeg_queue import ffmpeg_queue
from .models import Job, WatermarkType
from .schemas import (
    JobCreateResponse,
    JobDetail,
    JobListItem,
    SettingsResponse,
    SettingsUpdate,
    WatermarkSettingsIn,
)


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_routes(app)
    static_dir = Path(__file__).resolve().parents[2] / "frontend" / "assets"
    if static_dir.exists():
        app.mount("/assets", StaticFiles(directory=static_dir), name="assets")
    return app


def register_routes(app: FastAPI) -> None:
    prefix = settings.api_prefix

    @app.get("/", response_class=HTMLResponse)
    async def root() -> str:
        index_path = Path(__file__).resolve().parents[2] / "frontend" / "index.html"
        if not index_path.exists():
            raise HTTPException(status_code=404, detail="Frontend not found")
        return index_path.read_text(encoding="utf-8")

    @app.post(f"{prefix}/jobs", response_model=JobCreateResponse)
    async def create_job(
        files: List[UploadFile] = File(..., description="Input video files"),
        watermark_type: WatermarkType = Form(...),
        watermark_text: Optional[str] = Form(None),
        watermark_image: Optional[UploadFile] = File(
            None, description="PNG watermark image with transparency"
        ),
        watermark_image_path: Optional[str] = Form(None),
        font_size: int = Form(36),
        color: str = Form("white"),
        opacity: float = Form(1.0),
        position: str = Form("top-right"),
        offset_x: int = Form(20),
        offset_y: int = Form(20),
        font_path: Optional[str] = Form(None),
        output_format: Optional[str] = Form(None),
        target_device: str = Form("cpu"),
        preset: Optional[str] = Form(None),
    ) -> JobCreateResponse:
        if not files:
            raise HTTPException(status_code=400, detail="No video files provided")
        if watermark_type == WatermarkType.TEXT and not watermark_text:
            raise HTTPException(status_code=400, detail="Text watermark requires text")

        watermark_file_path: Optional[str] = None
        if watermark_type == WatermarkType.IMAGE:
            if watermark_image is not None:
                watermark_file_path = await _save_watermark_image(watermark_image)
            elif watermark_image_path:
                watermark_file_path = watermark_image_path
            else:
                raise HTTPException(status_code=400, detail="Image watermark requires file")

        saved_files = ffmpeg_queue.save_uploads(files)
        watermark_payload = WatermarkSettingsIn(
            type=watermark_type,
            text=watermark_text,
            font_path=font_path,
            font_size=font_size,
            color=color,
            image_path=watermark_file_path,
            opacity=opacity,
            position=position,  # type: ignore[arg-type]
            offset_x=offset_x,
            offset_y=offset_y,
        )
        metadata: Dict[str, str] = {}
        if preset:
            metadata["preset"] = preset
        metadata["ffmpeg_binary"] = settings.ffmpeg_binary
        if target_device != "cpu" and not settings.allow_gpu:
            target_device = "cpu"

        job = ffmpeg_queue.create_job(
            files=saved_files,
            watermark=watermark_payload,
            output_format=output_format,
            target_device=target_device,
            metadata=metadata,
        )
        return JobCreateResponse(job_id=job.id)

    @app.get(f"{prefix}/jobs", response_model=List[JobListItem])
    async def list_jobs() -> List[JobListItem]:
        jobs = ffmpeg_queue.list_jobs()
        return [
            JobListItem(
                id=job.id,
                status=job.status,
                progress=job.progress,
                created_at=job.created_at,
                started_at=job.started_at,
                finished_at=job.finished_at,
            )
            for job in jobs
        ]

    @app.get(f"{prefix}/jobs/{{job_id}}", response_model=JobDetail)
    async def get_job(job_id: str) -> JobDetail:
        job = ffmpeg_queue.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        return _job_to_detail(job)

    @app.get(f"{prefix}/jobs/{{job_id}}/log")
    async def get_job_log(job_id: str) -> Dict[str, List[str]]:
        job = ffmpeg_queue.get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")
        return {"log": job.log}

    @app.get(f"{prefix}/settings", response_model=SettingsResponse)
    async def get_settings() -> SettingsResponse:
        return SettingsResponse(
            max_parallel_jobs=settings.max_parallel_jobs,
            allow_gpu=settings.allow_gpu,
            default_output_format=settings.default_output_format,
            ffmpeg_binary=settings.ffmpeg_binary,
        )

    @app.patch(f"{prefix}/settings")
    async def update_settings(payload: SettingsUpdate) -> SettingsResponse:
        ffmpeg_queue.update_settings(payload)
        return SettingsResponse(
            max_parallel_jobs=settings.max_parallel_jobs,
            allow_gpu=settings.allow_gpu,
            default_output_format=settings.default_output_format,
            ffmpeg_binary=settings.ffmpeg_binary,
        )


async def _save_watermark_image(upload: UploadFile) -> str:
    extension = Path(upload.filename or "watermark.png").suffix or ".png"
    file_name = f"watermark_{uuid.uuid4().hex}{extension}"
    destination = settings.upload_path / file_name
    with destination.open("wb") as buffer:
        buffer.write(await upload.read())
    return str(destination)


def _job_to_detail(job: Job) -> JobDetail:
    watermark = job.watermark
    return JobDetail(
        id=job.id,
        status=job.status,
        progress=job.progress,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        watermark=WatermarkSettingsIn(
            type=watermark.type,
            text=watermark.text,
            font_path=watermark.font_path,
            font_size=watermark.font_size,
            color=watermark.color,
            image_path=str(watermark.image_path) if watermark.image_path else None,
            opacity=watermark.opacity,
            position=watermark.position,
            offset_x=watermark.offset_x,
            offset_y=watermark.offset_y,
        ),
        output_format=job.output_format,
        output_dir=str(job.output_dir),
        target_device=job.target_device,
        metadata=job.metadata,
        log=job.log,
        input_files=[str(path) for path in job.input_files],
    )


app = create_app()


app = create_app()
