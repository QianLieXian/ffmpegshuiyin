from __future__ import annotations

import queue
import shutil
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import UploadFile

from .config import settings
from .models import Job, JobStatus, WatermarkSettings
from .schemas import SettingsUpdate, WatermarkSettingsIn
from .watermark import build_ffmpeg_command, command_as_string


class FFmpegQueue:
    """A lightweight FFmpeg processing queue with worker threads."""

    def __init__(self) -> None:
        self._jobs: Dict[str, Job] = {}
        self._queue: "queue.Queue[str]" = queue.Queue()
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._workers: List[threading.Thread] = []
        self._max_parallel_jobs = settings.max_parallel_jobs
        self._start_workers()

    # ------------------------------------------------------------------
    # Job management
    # ------------------------------------------------------------------
    def create_job(
        self,
        files: List[Path],
        watermark: WatermarkSettingsIn,
        output_format: Optional[str] = None,
        target_device: str = "cpu",
        metadata: Optional[Dict[str, str]] = None,
    ) -> Job:
        if target_device not in {"cpu", "intel", "nvidia"}:
            target_device = "cpu"
        if target_device != "cpu" and not settings.allow_gpu:
            target_device = "cpu"
        wm_settings = WatermarkSettings(
            type=watermark.type,
            text=watermark.text,
            font_path=watermark.font_path,
            font_size=watermark.font_size,
            color=watermark.color,
            image_path=Path(watermark.image_path) if watermark.image_path else None,
            opacity=watermark.opacity,
            position=watermark.position,
            offset_x=watermark.offset_x,
            offset_y=watermark.offset_y,
        )
        output_dir = settings.output_path
        job = Job(
            input_files=files,
            watermark=wm_settings,
            output_format=output_format or settings.default_output_format,
            output_dir=output_dir,
            target_device=target_device,
        )
        job.metadata.update(metadata or {})
        job.metadata.setdefault("ffmpeg_binary", settings.ffmpeg_binary)
        with self._lock:
            self._jobs[job.id] = job
        job.append_log("Job created and queued")
        self._queue.put(job.id)
        return job

    def list_jobs(self) -> List[Job]:
        with self._lock:
            return list(self._jobs.values())

    def get_job(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    # ------------------------------------------------------------------
    # Worker lifecycle
    # ------------------------------------------------------------------
    def _start_workers(self) -> None:
        for _ in range(self._max_parallel_jobs):
            worker = threading.Thread(target=self._worker, daemon=True)
            worker.start()
            self._workers.append(worker)

    def _worker(self) -> None:
        while not self._stop_event.is_set():
            try:
                job_id = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if job_id == "__stop__":
                self._queue.task_done()
                break
            job = self.get_job(job_id)
            if job is None:
                self._queue.task_done()
                continue
            try:
                self._run_job(job)
            finally:
                self._queue.task_done()

    def shutdown(self) -> None:
        self._stop_event.set()
        for _ in self._workers:
            self._queue.put("__stop__")
        for worker in self._workers:
            worker.join(timeout=1)

    # ------------------------------------------------------------------
    # Settings management
    # ------------------------------------------------------------------
    def update_settings(self, payload: SettingsUpdate) -> None:
        changed = False
        if payload.max_parallel_jobs is not None and payload.max_parallel_jobs != self._max_parallel_jobs:
            self._max_parallel_jobs = payload.max_parallel_jobs
            self._resize_workers()
            settings.max_parallel_jobs = self._max_parallel_jobs
            changed = True
        if payload.default_output_format is not None:
            settings.default_output_format = payload.default_output_format
            changed = True
        if payload.ffmpeg_binary is not None:
            settings.ffmpeg_binary = payload.ffmpeg_binary
            changed = True
        if payload.allow_gpu is not None:
            settings.allow_gpu = payload.allow_gpu
            changed = True
        if changed:
            for job in self.list_jobs():
                job.metadata.setdefault("ffmpeg_binary", settings.ffmpeg_binary)

    def _resize_workers(self) -> None:
        current = len(self._workers)
        if self._max_parallel_jobs > current:
            for _ in range(self._max_parallel_jobs - current):
                worker = threading.Thread(target=self._worker, daemon=True)
                worker.start()
                self._workers.append(worker)
        elif self._max_parallel_jobs < current:
            # signal threads to exit gracefully by posting sentinel None
            for _ in range(current - self._max_parallel_jobs):
                self._queue.put("__stop__")
            self._workers = [w for w in self._workers if w.is_alive()]

    # ------------------------------------------------------------------
    # Job execution
    # ------------------------------------------------------------------
    def _run_job(self, job: Job) -> None:
        if job.status in {JobStatus.CANCELLED, JobStatus.COMPLETED}:
            return
        job.status = JobStatus.RUNNING
        job.started_at = time.time()
        total_files = len(job.input_files)
        job.append_log(f"Starting job with {total_files} file(s)")

        for index, input_file in enumerate(job.input_files, start=1):
            try:
                output_filename = f"{input_file.stem}_watermarked.{job.output_format}"
                output_path = job.output_dir / output_filename
                output_path.parent.mkdir(parents=True, exist_ok=True)
                cmd = build_ffmpeg_command(job, input_file, output_path)
                job.append_log(f"Processing {input_file.name} -> {output_path.name}")
                job.append_log(f"Command: {command_as_string(cmd)}")
                self._execute_ffmpeg(job, cmd)
                job.append_log(f"Completed {input_file.name}")
            except Exception as exc:  # noqa: BLE001
                job.status = JobStatus.FAILED
                job.finished_at = time.time()
                job.append_log(f"Failed: {exc}")
                return
            job.progress = index / total_files

        job.status = JobStatus.COMPLETED
        job.finished_at = time.time()
        job.append_log("Job finished successfully")

    def _execute_ffmpeg(self, job: Job, cmd: List[str]) -> None:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
        )
        assert process.stdout is not None
        for line in process.stdout:
            job.append_log(line.strip())
        return_code = process.wait()
        if return_code != 0:
            raise RuntimeError(f"FFmpeg exited with code {return_code}")

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------
    def save_uploads(self, files: List[UploadFile]) -> List[Path]:
        saved_files: List[Path] = []
        for file in files:
            suffix = Path(file.filename).suffix
            unique_name = f"input_{uuid.uuid4().hex}{suffix}"
            destination = settings.upload_path / unique_name
            file.file.seek(0)
            with destination.open("wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            saved_files.append(destination)
        return saved_files


ffmpeg_queue = FFmpegQueue()
