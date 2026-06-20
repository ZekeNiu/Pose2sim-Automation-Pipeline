from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from .models import EnvironmentStatus
from .paths import SPORTS3D_PYTHON


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
    if not python_path.exists():
        errors.append(f"找不到 Python: {python_path}")
        return EnvironmentStatus(python_path, None, None, None, None, None, shutil.which("ffmpeg"), "未知", errors)

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
    }
    for key, label in required.items():
        if not data.get(key):
            errors.append(f"缺少 {label}。")

    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        errors.append("缺少 ffmpeg，无法稳定处理手机视频旋转和浏览器兼容转码。")

    return EnvironmentStatus(
        python_path=Path(data.get("python") or python_path),
        pose2sim_version=data.get("pose2sim"),
        opensim_version=data.get("opensim"),
        customtkinter_version=data.get("customtkinter"),
        plotly_version=data.get("plotly"),
        openpyxl_version=data.get("openpyxl"),
        ffmpeg_path=ffmpeg_path,
        gpu_hint=data.get("gpu_hint", "未知"),
        errors=errors,
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

