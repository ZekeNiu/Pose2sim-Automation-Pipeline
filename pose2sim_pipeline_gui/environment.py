from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from .models import EnvironmentStatus
from .paths import SPORTS3D_PYTHON


VERIFIED_POSE2SIM_VERSION = "0.10.43"

CHECK_SCRIPT = r"""
import importlib.metadata as md
import json
import sys

def version(name):
    try:
        return md.version(name)
    except Exception:
        return None

data = {
    "python": sys.executable,
    "pose2sim": version("pose2sim"),
    "opensim": None,
    "customtkinter": version("customtkinter"),
    "plotly": version("plotly"),
    "openpyxl": version("openpyxl"),
    "pandas": version("pandas"),
    "pillow": version("pillow"),
    "toml": version("toml"),
    "gpu_hint": "CPU",
}
try:
    import opensim
    data["opensim"] = getattr(opensim, "__version__", "imported")
except Exception as exc:
    data["opensim_error"] = repr(exc)
try:
    import onnxruntime as ort
    providers = ort.get_available_providers()
    data["gpu_hint"] = "CUDA 可用" if any("CUDA" in p for p in providers) else "CPU / OpenVINO"
except Exception:
    pass
print(json.dumps(data, ensure_ascii=False))
"""


def check_environment(python_path: Path = SPORTS3D_PYTHON) -> EnvironmentStatus:
    errors: list[str] = []
    warnings: list[str] = []
    if not python_path.exists():
        errors.append(f"找不到 Python: {python_path}")
        return EnvironmentStatus(
            python_path=python_path,
            pose2sim_version=None,
            opensim_version=None,
            customtkinter_version=None,
            plotly_version=None,
            openpyxl_version=None,
            ffmpeg_path=shutil.which("ffmpeg"),
            gpu_hint="未知",
            errors=errors,
            ffprobe_path=shutil.which("ffprobe"),
            warnings=warnings,
        )

    try:
        result = subprocess.run(
            [str(python_path), "-c", CHECK_SCRIPT],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        data = json.loads(result.stdout.strip().splitlines()[-1])
    except Exception as exc:
        errors.append(f"无法执行环境检查: {exc}")
        data = {}

    required = {
        "pose2sim": "Pose2Sim",
        "opensim": "OpenSim",
        "customtkinter": "customtkinter",
        "plotly": "plotly",
        "openpyxl": "openpyxl",
        "pandas": "pandas",
        "pillow": "Pillow",
        "toml": "toml",
    }
    for key, label in required.items():
        if not data.get(key):
            errors.append(f"缺少 {label}。")

    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        errors.append("缺少 ffmpeg，无法稳定处理手机视频旋转和浏览器兼容转码。")
    ffprobe_path = shutil.which("ffprobe")
    if not ffprobe_path:
        warnings.append("缺少 ffprobe，视频分辨率、帧率和旋转信息预览可能不完整。")

    pose2sim_version = data.get("pose2sim")
    if pose2sim_version and pose2sim_version != VERIFIED_POSE2SIM_VERSION:
        warnings.append(
            f"当前 Pose2Sim 为 {pose2sim_version}；本 GUI 主要按 {VERIFIED_POSE2SIM_VERSION} 验证，"
            "最新版可能带来配置字段或模型下载变化。"
        )

    return EnvironmentStatus(
        python_path=Path(data.get("python") or python_path),
        pose2sim_version=pose2sim_version,
        opensim_version=data.get("opensim"),
        customtkinter_version=data.get("customtkinter"),
        plotly_version=data.get("plotly"),
        openpyxl_version=data.get("openpyxl"),
        ffmpeg_path=ffmpeg_path,
        gpu_hint=data.get("gpu_hint", "未知"),
        errors=errors,
        pandas_version=data.get("pandas"),
        pillow_version=data.get("pillow"),
        toml_version=data.get("toml"),
        ffprobe_path=ffprobe_path,
        warnings=warnings,
    )


def update_pose2sim(python_path: Path = SPORTS3D_PYTHON) -> subprocess.Popen:
    return subprocess.Popen(
        [str(python_path), "-m", "pip", "install", "--upgrade", "pose2sim"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
