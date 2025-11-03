from __future__ import annotations

import shlex
from pathlib import Path
from typing import List, Tuple

from .models import Job, WatermarkType


POSITION_MAP = {
    "top-left": ("{x_offset}", "{y_offset}"),
    "top-right": ("W-w-{x_offset}", "{y_offset}"),
    "bottom-left": ("{x_offset}", "H-h-{y_offset}"),
    "bottom-right": ("W-w-{x_offset}", "H-h-{y_offset}"),
    "center": ("(W-w)/2", "(H-h)/2"),
}


def escape_text(text: str) -> str:
    """Escape text for ffmpeg drawtext."""
    escaped = text.replace("\\", "\\\\").replace(":", "\\:")
    return escaped.replace("'", "\\\'")


def build_filter_and_inputs(job: Job) -> Tuple[List[str], List[str]]:
    """Return additional inputs and filter args for ffmpeg."""
    watermark = job.watermark
    filter_complex: List[str] = []
    extra_inputs: List[str] = []

    x_expr, y_expr = POSITION_MAP[watermark.position]
    x_expr = x_expr.format(x_offset=watermark.offset_x)
    y_expr = y_expr.format(y_offset=watermark.offset_y)

    if watermark.type == WatermarkType.TEXT:
        color = watermark.color
        if watermark.opacity < 1.0:
            # ffmpeg expects color@alpha
            color = f"{color}@{watermark.opacity:.2f}"
        drawtext_args = {
            "text": escape_text(watermark.text or ""),
            "fontcolor": color,
            "fontsize": watermark.font_size,
            "x": x_expr,
            "y": y_expr,
        }
        if watermark.font_path:
            drawtext_args["fontfile"] = watermark.font_path
        drawtext_expr = ":".join(f"{key}={value}" for key, value in drawtext_args.items())
        filter_complex.append(f"drawtext={drawtext_expr}")
    else:
        if not watermark.image_path:
            raise ValueError("Image watermark requires an image path")
        image_path = Path(watermark.image_path)
        extra_inputs.extend(["-i", str(image_path)])
        overlay = f"[1]format=rgba,colorchannelmixer=aa={watermark.opacity:.2f}[wm];"
        overlay += f"[0][wm]overlay={x_expr}:{y_expr}"
        filter_complex.append(overlay)

    return extra_inputs, filter_complex


def build_ffmpeg_command(job: Job, input_file: Path, output_file: Path) -> List[str]:
    inputs, filters = build_filter_and_inputs(job)
    cmd: List[str] = [job.metadata.get("ffmpeg_binary", "ffmpeg"), "-y", "-i", str(input_file)]
    cmd.extend(inputs)
    if filters:
        cmd.extend(["-filter_complex", ";".join(filters)])
    if job.target_device == "cpu":
        cmd.extend(["-c:v", "libx264", "-preset", job.metadata.get("preset", "medium")])
    elif job.target_device == "intel":
        cmd.extend(["-c:v", "h264_qsv"])
    elif job.target_device == "nvidia":
        cmd.extend(["-c:v", "h264_nvenc"])
    cmd.extend(["-c:a", "copy", str(output_file)])
    return cmd


def command_as_string(cmd: List[str]) -> str:
    return " ".join(shlex.quote(part) for part in cmd)
