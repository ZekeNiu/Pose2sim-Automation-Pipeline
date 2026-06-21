from __future__ import annotations

import re
import os
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
PROJECTS_DIR = WORKSPACE_ROOT / "projects"
OUTPUTS_DIR = WORKSPACE_ROOT / "outputs"
ASSETS_DIR = WORKSPACE_ROOT / "assets"
CHECKERBOARD_DIR = ASSETS_DIR / "checkerboards"
GENERATED_CHECKERBOARD_DIR = CHECKERBOARD_DIR / "generated"
DEFAULT_SPORTS3D_PYTHON = Path(r"D:\Application\Anaconda\envs\sports3d\python.exe")
SPORTS3D_PYTHON = Path(os.environ.get("POSE2SIM_GUI_PYTHON", str(DEFAULT_SPORTS3D_PYTHON)))

WINDOWS_INVALID_CHARS = r'<>:"/\|?*'


def ensure_workspace() -> None:
    for directory in [PROJECTS_DIR, OUTPUTS_DIR, GENERATED_CHECKERBOARD_DIR]:
        directory.mkdir(parents=True, exist_ok=True)


def sanitize_project_name(name: str) -> str:
    cleaned = name.strip()
    cleaned = "".join("_" if ch in WINDOWS_INVALID_CHARS else ch for ch in cleaned)
    cleaned = re.sub(r"\s+", "_", cleaned)
    cleaned = cleaned.strip("._ ")
    if not cleaned:
        raise ValueError("项目名称不能为空。")
    if cleaned in {".", ".."}:
        raise ValueError("项目名称不能是特殊路径。")
    return cleaned[:80]


def assert_under_workspace(path: Path) -> Path:
    resolved = path.resolve()
    root = WORKSPACE_ROOT.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"路径必须位于工作区内: {resolved}") from exc
    return resolved


def project_dir(project_name: str) -> Path:
    return assert_under_workspace(PROJECTS_DIR / sanitize_project_name(project_name))


def output_dir(project_name: str) -> Path:
    return assert_under_workspace(OUTPUTS_DIR / sanitize_project_name(project_name))
