from __future__ import annotations

import json
import inspect
import shutil
import subprocess
from pathlib import Path

from .models import EnvironmentStatus
from .paths import SPORTS3D_PYTHON


VERIFIED_POSE2SIM_VERSION = "0.10.47"
POSE2SIM_NEW_INSTALL_MIN_VERSION = "0.10.44"
POSE2SIM_NEW_INSTALL_MIN_PYTHON = (3, 11, 0)

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
    "python_version": sys.version.split()[0],
    "python_version_info": list(sys.version_info[:3]),
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


def version_tuple(version: str | None) -> tuple[int, ...]:
    if not version:
        return ()
    numbers: list[int] = []
    for part in version.replace("-", ".").split("."):
        if not part.isdigit():
            digits = "".join(ch for ch in part if ch.isdigit())
            if not digits:
                break
            part = digits
        numbers.append(int(part))
    return tuple(numbers)


def version_at_least(version: str | None, minimum: str) -> bool:
    current = version_tuple(version)
    required = version_tuple(minimum)
    if not current:
        return False
    width = max(len(current), len(required))
    return current + (0,) * (width - len(current)) >= required + (0,) * (width - len(required))


def python_version_at_least(
    python_version_info: tuple[int, int, int] | list[int] | None,
    minimum: tuple[int, int, int] = POSE2SIM_NEW_INSTALL_MIN_PYTHON,
) -> bool:
    if python_version_info is None:
        return False
    current = tuple(int(part) for part in python_version_info[:3])
    return current >= minimum


def installed_pose2sim_version() -> str | None:
    try:
        import importlib.metadata as md

        return md.version("pose2sim")
    except Exception:
        return None


def pose2sim_uses_percent_trimmed_extrema(version: str | None = None) -> bool:
    return version_at_least(version or installed_pose2sim_version(), POSE2SIM_NEW_INSTALL_MIN_VERSION)


def pose2sim_supports_lower_body(version: str | None = None) -> bool:
    return version_at_least(version or installed_pose2sim_version(), POSE2SIM_NEW_INSTALL_MIN_VERSION)


def pose2sim_intrinsics_video_extraction_bug_present() -> bool:
    try:
        from Pose2Sim import calibration
    except Exception:
        return False

    try:
        source = inspect.getsource(calibration.extract_frames)
    except Exception:
        version = installed_pose2sim_version()
        return version_at_least(version, "0.10.47") and not version_at_least(version, "0.10.48")

    return "Path(video_path).exists().stem" in source.replace(" ", "")


def _python_info_from_data(data: dict) -> tuple[int, int, int] | None:
    raw = data.get("python_version_info")
    if isinstance(raw, list) and len(raw) >= 3:
        return int(raw[0]), int(raw[1]), int(raw[2])
    return None


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
    python_version_info = _python_info_from_data(data)
    if python_version_info and not python_version_at_least(python_version_info):
        version_label = ".".join(str(part) for part in python_version_info)
        warnings.append(
            f"当前 Python 为 {version_label}；Pose2Sim {POSE2SIM_NEW_INSTALL_MIN_VERSION}+ 需要 Python >= 3.11，"
            "此环境的一键更新通常只能停在 0.10.43。若要使用 0.10.47，请切换到 Python 3.11 或更新环境。"
        )
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
        python_version=data.get("python_version"),
        python_version_info=python_version_info,
    )


def summarize_pose2sim_update(status: EnvironmentStatus, return_code: int) -> tuple[str, bool]:
    if return_code != 0:
        return f"更新命令退出码为 {return_code}，请查看环境页日志。", True
    if version_at_least(status.pose2sim_version, VERIFIED_POSE2SIM_VERSION):
        return f"Pose2Sim 已是 {status.pose2sim_version}，环境检查已刷新。", False
    if not python_version_at_least(status.python_version_info):
        return (
            "更新命令已结束，但当前 Python 不支持 Pose2Sim 0.10.44+。"
            f"当前检测到 Pose2Sim {status.pose2sim_version or '未安装'}；"
            "请切换到 Python 3.11 或更新环境后再安装 0.10.47。",
            True,
        )
    return (
        f"更新命令已结束，但当前 Pose2Sim 仍为 {status.pose2sim_version or '未安装'}，"
        "未达到 GUI 验证版本 0.10.47。请查看环境页日志确认 pip 源或网络情况。",
        True,
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
