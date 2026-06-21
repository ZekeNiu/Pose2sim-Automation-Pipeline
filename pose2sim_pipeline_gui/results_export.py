from __future__ import annotations

import shutil
from importlib.resources import files
from pathlib import Path

from .paths import assert_under_workspace


RESULT_DIRECTORIES = [
    "calibration",
    "pose",
    "pose-sync",
    "pose-associated",
    "pose-3d",
    "kinematics",
]

ROOT_RESULT_FILES = [
    "Config.toml",
    "logs.txt",
    "opensim.log",
]


def _needs_copy(source: Path, target: Path) -> bool:
    if not target.exists():
        return True
    source_stat = source.stat()
    target_stat = target.stat()
    if source_stat.st_size != target_stat.st_size:
        return True
    return int(source_stat.st_mtime) != int(target_stat.st_mtime)


def _copy_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if _needs_copy(source, target):
        shutil.copy2(source, target)


def _sync_directory(source: Path, target: Path) -> None:
    if not source.exists():
        return
    assert_under_workspace(target)
    for file_path in source.rglob("*"):
        if not file_path.is_file():
            continue
        relative = file_path.relative_to(source)
        _copy_file(file_path, target / relative)


def _copy_opensim_geometry(target_kinematics_dir: Path) -> None:
    try:
        source = Path(str(files("Pose2Sim") / "OpenSim_Setup" / "Geometry"))
    except Exception:
        return
    if source.exists():
        _sync_directory(source, target_kinematics_dir / "Geometry")


def _write_opensim_readme(target_kinematics_dir: Path) -> None:
    target_kinematics_dir.mkdir(parents=True, exist_ok=True)
    readme = target_kinematics_dir / "OpenSim_查看说明.txt"
    readme.write_text(
        "OpenSim 查看顺序：\n"
        "1. 先在 OpenSim 中打开本目录下的 .osim 模型。\n"
        "2. 再加载同名或对应的 .mot 运动文件。\n"
        "3. 如果模型没有骨架外观，请确认本目录下是否有 Geometry 文件夹，或在 OpenSim 中设置 Geometry 搜索路径。\n"
        "4. 如果模型明显失真，优先检查校准外参、同步、遮挡、IK marker error 和身高/体重输入；这通常不是 .mot 文件缺失造成的。\n",
        encoding="utf-8",
    )


def _export_single_project(project_dir: Path, output_dir: Path) -> None:
    for dirname in RESULT_DIRECTORIES:
        _sync_directory(project_dir / dirname, output_dir / dirname)
    for filename in ROOT_RESULT_FILES:
        source = project_dir / filename
        if source.exists() and source.is_file():
            _copy_file(source, output_dir / filename)
    kinematics_dir = output_dir / "kinematics"
    if any(kinematics_dir.glob("*.osim")) or any(kinematics_dir.glob("*.mot")):
        _copy_opensim_geometry(kinematics_dir)
        _write_opensim_readme(kinematics_dir)



def _is_trial_dir(path: Path) -> bool:
    if not path.is_dir() or path.name.startswith("."):
        return False
    if path.name.lower() in {"source", "videos", "calibration", "pose", "pose-sync", "pose-associated", "pose-3d", "kinematics"}:
        return False
    return (path / "Config.toml").exists() or any((path / dirname).exists() for dirname in RESULT_DIRECTORIES)


def export_pose2sim_outputs(project_dir: Path, output_dir: Path) -> None:
    """Copy Pose2Sim-generated outputs to the user-facing output directory.

    Pose2Sim writes into the project directory by design. This exporter mirrors
    generated results into outputs/<project> without duplicating source inputs.
    """

    project_dir = assert_under_workspace(project_dir)
    output_dir = assert_under_workspace(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    trial_dirs = sorted(child for child in project_dir.iterdir() if _is_trial_dir(child)) if project_dir.exists() else []
    has_root_results = any((project_dir / dirname).exists() for dirname in RESULT_DIRECTORIES) or any(
        (project_dir / filename).exists() for filename in ROOT_RESULT_FILES
    )

    if trial_dirs:
        if has_root_results:
            _export_single_project(project_dir, output_dir / "_root")
        for trial_dir in trial_dirs:
            _export_single_project(trial_dir, output_dir / trial_dir.name)
    else:
        _export_single_project(project_dir, output_dir)
