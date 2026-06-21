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


def calibration_frame_interval(fps: float, extract_every_N_sec: float) -> float:
    rounded_fps = round(fps)
    interval = rounded_fps * extract_every_N_sec
    if rounded_fps <= 0 or interval <= 0:
        raise RuntimeError("内参视频抽帧失败：无法读取有效帧率，请检查视频文件是否可正常打开。")
    return interval


def should_extract_calibration_frame(frame_number: int, fps: float, extract_every_N_sec: float) -> bool:
    return frame_number % calibration_frame_interval(fps, extract_every_N_sec) == 0


def _generated_calibration_frames(output_dir: Path, video_stem: str) -> list[Path]:
    return sorted(output_dir.glob(f"{video_stem}_[0-9][0-9][0-9][0-9][0-9].png"))


def extract_calibration_video_frames(
    video_path: Path,
    output_dir: Path | None = None,
    *,
    extract_every_N_sec: float = 1.0,
    overwrite: bool = False,
) -> list[Path]:
    video_path = Path(video_path)
    output_dir = Path(output_dir) if output_dir is not None else video_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    if not video_path.exists():
        raise RuntimeError(f"内参视频抽帧失败：找不到视频文件 {video_path}")

    existing = _generated_calibration_frames(output_dir, video_path.stem)
    if existing and not overwrite:
        return existing
    if overwrite:
        for frame_path in existing:
            frame_path.unlink(missing_ok=True)

    try:
        import cv2
    except Exception as exc:
        raise RuntimeError("内参视频抽帧失败：当前 Python 环境无法导入 OpenCV(cv2)。") from exc

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        capture.release()
        raise RuntimeError(f"内参视频抽帧失败：OpenCV 无法打开 {video_path}")

    fps = round(capture.get(cv2.CAP_PROP_FPS))
    interval = calibration_frame_interval(fps, extract_every_N_sec)
    generated: list[Path] = []
    frame_number = 0

    try:
        while capture.isOpened():
            ok, frame = capture.read()
            if not ok:
                break
            if frame_number % interval == 0:
                image_path = output_dir / f"{video_path.stem}_{frame_number:05d}.png"
                if not cv2.imwrite(str(image_path), frame):
                    raise RuntimeError(f"内参视频抽帧失败：无法写入图片 {image_path}")
                generated.append(image_path)
            frame_number += 1
    finally:
        capture.release()

    if not generated:
        raise RuntimeError(
            "内参视频抽帧失败：没有生成任何 PNG。请检查 OpenCV、视频可读性，以及棋盘格内参视频是否有效。"
        )
    return generated


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
