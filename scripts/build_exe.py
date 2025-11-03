"""PyInstaller build helper for bundling the backend and frontend into a single executable."""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
FRONTEND_DIR = PROJECT_ROOT / "frontend"


def build(spec_path: Path | None = None) -> None:
    if spec_path is None:
        spec_path = PROJECT_ROOT / "ffmpegshuiyin.spec"
    sep = ';' if os.name == 'nt' else ':'
    command = [
        "pyinstaller",
        "--noconfirm",
        "--clean",
        "--add-data",
        f"{FRONTEND_DIR}{sep}frontend",
        "--name",
        "ffmpegshuiyin",
        str(BACKEND_DIR / "app" / "main.py"),
    ]
    if spec_path.exists():
        command = ["pyinstaller", str(spec_path)]
    print("Running:", " ".join(command))
    subprocess.check_call(command)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build executable for FFmpeg Shuiyin")
    parser.add_argument("--spec", type=Path, default=None, help="Optional custom spec file")
    args = parser.parse_args()
    build(args.spec)


if __name__ == "__main__":
    main()
