from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class VideoInfo:
    path: Path
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    duration: float | None = None
    rotation: int = 0


def _parse_fps(value: str | None) -> float | None:
    if not value or value == "0/0":
        return None
    if "/" in value:
        num, den = value.split("/", 1)
        try:
            return float(num) / float(den)
        except ZeroDivisionError:
            return None
    return float(value)


def inspect_video(path: Path) -> VideoInfo:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return VideoInfo(path=path)
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,r_frame_rate,duration:stream_tags=rotate:stream_side_data=rotation",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        return VideoInfo(path=path)
    data = json.loads(result.stdout or "{}")
    stream = (data.get("streams") or [{}])[0]
    rotation = 0
    tags = stream.get("tags") or {}
    if tags.get("rotate"):
        rotation = int(float(tags["rotate"]))
    for item in stream.get("side_data_list") or []:
        if "rotation" in item:
            rotation = int(float(item["rotation"]))
    duration = stream.get("duration")
    return VideoInfo(
        path=path,
        width=stream.get("width"),
        height=stream.get("height"),
        fps=_parse_fps(stream.get("r_frame_rate")),
        duration=float(duration) if duration else None,
        rotation=rotation,
    )


def build_normalize_command(input_path: Path, output_path: Path) -> list[str]:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("找不到 ffmpeg。")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    return [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-i",
        str(input_path),
        "-map",
        "0:v:0",
        "-an",
        "-vf",
        "scale=trunc(iw/2)*2:trunc(ih/2)*2",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "23",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        "-metadata:s:v:0",
        "rotate=0",
        str(output_path),
    ]


def normalize_video(input_path: Path, output_path: Path) -> VideoInfo:
    command = build_normalize_command(input_path, output_path)
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"视频转码失败: {result.stdout}\n{result.stderr}")
    return inspect_video(output_path)

