from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import toml

from .paths import SPORTS3D_PYTHON, WORKSPACE_ROOT, assert_under_workspace


CALISCOPE_EXPORT_NAME = "camera_array_aniposelib.toml"
POSE2SIM_CALISCOPE_NAME = "Calib_caliscope.toml"
CAMERA_REQUIRED_FIELDS = ("size", "matrix", "distortions", "rotation", "translation")
IGNORED_TOML_SECTIONS = {"metadata", "capture_volume", "charuco", "checkerboard"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".m4v", ".webm"}


@dataclass(frozen=True)
class CaliscopeValidation:
    camera_count: int
    camera_names: list[str]


@dataclass(frozen=True)
class CaliscopeImportResult:
    source_path: Path
    target_path: Path
    camera_count: int
    config_path: Path
    config_changed: bool
    archived_calibration_path: Path | None = None
    config_backup_path: Path | None = None


@dataclass(frozen=True)
class CaliscopePreparedCamera:
    camera_label: str
    caliscope_id: int
    intrinsic_source: Path
    extrinsic_source: Path
    intrinsic_target: Path
    extrinsic_target: Path


@dataclass(frozen=True)
class CaliscopeWorkspacePrepResult:
    workspace_dir: Path
    cameras: list[CaliscopePreparedCamera]

    @property
    def camera_count(self) -> int:
        return len(self.cameras)


def caliscope_workspace_dir(project_dir: Path) -> Path:
    return project_dir / "caliscope_workspace"


def ensure_caliscope_workspace(project_dir: Path) -> Path:
    workspace_dir = assert_under_workspace(caliscope_workspace_dir(project_dir))
    workspace_dir.mkdir(parents=True, exist_ok=True)
    return workspace_dir


def _camera_sort_key(path: Path) -> int:
    digits = "".join(ch for ch in path.stem if ch.isdigit())
    return int(digits) if digits else 0


def _project_intrinsic_video(project_dir: Path, camera_label: str) -> Path | None:
    cam_dir = project_dir / "calibration" / "intrinsics" / camera_label
    if not cam_dir.exists():
        return None
    expected = cam_dir / f"{camera_label}_intrinsics.mp4"
    if expected.exists():
        return expected
    videos = sorted((path for path in cam_dir.iterdir() if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS))
    return videos[0] if videos else None


def _project_extrinsic_video(project_dir: Path, camera_label: str) -> Path | None:
    extrinsics_dir = project_dir / "calibration" / "extrinsics"
    expected = extrinsics_dir / f"{camera_label}.mp4"
    if expected.exists():
        return expected
    videos = sorted(extrinsics_dir.glob(f"{camera_label}.*"))
    for path in videos:
        if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS:
            return path
    return None


def _project_extrinsic_nonvideo(project_dir: Path, camera_label: str) -> Path | None:
    extrinsics_dir = project_dir / "calibration" / "extrinsics"
    for path in sorted(extrinsics_dir.glob(f"{camera_label}.*")):
        if path.is_file() and path.suffix.lower() not in VIDEO_EXTENSIONS:
            return path
    return None


def _project_camera_labels(project_dir: Path) -> list[str]:
    labels: set[str] = set()
    intrinsics_dir = project_dir / "calibration" / "intrinsics"
    if intrinsics_dir.exists():
        labels.update(path.name for path in intrinsics_dir.iterdir() if path.is_dir() and path.name.startswith("cam"))
    extrinsics_dir = project_dir / "calibration" / "extrinsics"
    if extrinsics_dir.exists():
        labels.update(path.stem for path in extrinsics_dir.iterdir() if path.is_file() and path.stem.startswith("cam"))
    return sorted(labels, key=lambda label: _camera_sort_key(Path(label)))


def _project_trial_video_count(project_dir: Path) -> int:
    videos_dir = project_dir / "videos"
    if not videos_dir.exists():
        return 0
    return len([path for path in videos_dir.iterdir() if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS])


def _replace_with_link_or_copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target.unlink()
    try:
        os.link(source, target)
    except OSError:
        shutil.copy2(source, target)


def _clear_prepared_caliscope_videos(workspace_dir: Path) -> None:
    for folder in (workspace_dir / "calibration" / "intrinsic", workspace_dir / "calibration" / "extrinsic"):
        if not folder.exists():
            continue
        for path in folder.glob("cam_*.mp4"):
            if path.is_file():
                path.unlink()


def prepare_caliscope_workspace(project_dir: Path) -> CaliscopeWorkspacePrepResult:
    workspace_dir = ensure_caliscope_workspace(project_dir)
    trial_video_count = _project_trial_video_count(project_dir)
    if trial_video_count < 2:
        raise ValueError("Caliscope 需要至少 2 个测试视频。请先在中文 GUI 中按机位顺序导入测试视频。")

    camera_labels = _project_camera_labels(project_dir)
    if len(camera_labels) < 2:
        raise ValueError("Caliscope 至少需要 2 个机位。请先在中文 GUI 中导入至少 2 组内参视频和外参视频。")

    source_pairs: list[tuple[str, Path, Path]] = []
    missing_intrinsics: list[str] = []
    missing_extrinsics: list[str] = []
    extrinsic_images: list[str] = []

    for camera_label in camera_labels:
        intrinsic_source = _project_intrinsic_video(project_dir, camera_label)
        extrinsic_source = _project_extrinsic_video(project_dir, camera_label)
        if intrinsic_source is None:
            missing_intrinsics.append(camera_label)
        if extrinsic_source is None:
            if _project_extrinsic_nonvideo(project_dir, camera_label) is not None:
                extrinsic_images.append(camera_label)
            else:
                missing_extrinsics.append(camera_label)
        if intrinsic_source is None or extrinsic_source is None:
            continue
        source_pairs.append((camera_label, intrinsic_source, extrinsic_source))

    messages: list[str] = []
    if missing_intrinsics:
        messages.append("缺少内参视频：" + "、".join(missing_intrinsics))
    if missing_extrinsics:
        messages.append("缺少外参视频：" + "、".join(missing_extrinsics))
    if extrinsic_images:
        messages.append(
            "Caliscope 需要重新导入外参视频；以下机位当前只有图片或非视频外参资料：" + "、".join(extrinsic_images)
        )
    if messages:
        raise ValueError("无法准备 Caliscope 工作区。\n" + "\n".join(messages))
    if len(source_pairs) < 2:
        raise ValueError("Caliscope 至少需要 2 个完整机位。请确认每个机位都已导入内参视频和外参视频。")
    if len(source_pairs) != trial_video_count:
        raise ValueError(
            f"Caliscope 校准视频机位数量是 {len(source_pairs)}，当前项目测试视频数量是 {trial_video_count}。"
            "请保持测试视频、内参视频、外参视频的机位数量一致。"
        )

    _clear_prepared_caliscope_videos(workspace_dir)
    prepared: list[CaliscopePreparedCamera] = []
    for caliscope_id, (camera_label, intrinsic_source, extrinsic_source) in enumerate(source_pairs):
        intrinsic_target = workspace_dir / "calibration" / "intrinsic" / f"cam_{caliscope_id}.mp4"
        extrinsic_target = workspace_dir / "calibration" / "extrinsic" / f"cam_{caliscope_id}.mp4"
        _replace_with_link_or_copy(intrinsic_source, intrinsic_target)
        _replace_with_link_or_copy(extrinsic_source, extrinsic_target)
        prepared.append(
            CaliscopePreparedCamera(
                camera_label=camera_label,
                caliscope_id=caliscope_id,
                intrinsic_source=intrinsic_source,
                extrinsic_source=extrinsic_source,
                intrinsic_target=intrinsic_target,
                extrinsic_target=extrinsic_target,
            )
        )

    return CaliscopeWorkspacePrepResult(workspace_dir=workspace_dir, cameras=prepared)


def _candidate_exports(workspace_dir: Path) -> list[Path]:
    if not workspace_dir.exists():
        return []
    exact_matches = [path for path in workspace_dir.rglob(CALISCOPE_EXPORT_NAME) if path.is_file()]
    fallback_matches = [
        path
        for path in workspace_dir.rglob("*.toml")
        if path.is_file() and "aniposelib" in path.name.lower() and path.name != CALISCOPE_EXPORT_NAME
    ]
    candidates = exact_matches + fallback_matches
    return sorted(candidates, key=lambda path: path.stat().st_mtime, reverse=True)


def find_caliscope_export(workspace_dir: Path) -> Path:
    candidates = _candidate_exports(workspace_dir)
    if not candidates:
        raise FileNotFoundError("没有找到 Caliscope 校准结果，请确认已在 Caliscope 中完成外参校准并保存。")
    return candidates[0]


def _camera_sections(data: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    sections: list[tuple[str, dict[str, Any]]] = []
    for name, value in data.items():
        if name in IGNORED_TOML_SECTIONS or not isinstance(value, dict):
            continue
        if any(field in value for field in CAMERA_REQUIRED_FIELDS):
            sections.append((name, value))
    return sections


def validate_caliscope_export(path: Path, expected_camera_count: int | None = None) -> CaliscopeValidation:
    try:
        data = toml.load(path)
    except Exception as exc:
        raise ValueError("Caliscope 校准结果无法读取，请回到 Caliscope 重新保存后再导入。") from exc

    cameras = _camera_sections(data)
    if not cameras:
        raise ValueError("没有找到可用于 Pose2Sim 的 Caliscope 校准结果，请确认已在 Caliscope 中完成外参校准并保存。")

    missing: list[str] = []
    for name, section in cameras:
        for field in CAMERA_REQUIRED_FIELDS:
            if field not in section:
                missing.append(f"{name}.{field}")
    if missing:
        raise ValueError("Caliscope 校准结果不完整，请回到 Caliscope 重新保存后再导入。缺少：" + "、".join(missing[:8]))

    camera_count = len(cameras)
    if expected_camera_count and camera_count != expected_camera_count:
        raise ValueError(
            f"Caliscope 中的相机数量是 {camera_count}，当前项目视频数量是 {expected_camera_count}，请保持两边机位数量一致。"
        )

    return CaliscopeValidation(camera_count=camera_count, camera_names=[name for name, _ in cameras])


def archive_existing_caliscope_calibration(calibration_dir: Path) -> Path | None:
    target = calibration_dir / POSE2SIM_CALISCOPE_NAME
    if not target.exists():
        return None
    archive_dir = assert_under_workspace(calibration_dir / "_archive")
    archive_dir.mkdir(parents=True, exist_ok=True)
    stamp = target.stat().st_mtime_ns
    archive_path = archive_dir / f"{target.stem}_{stamp}{target.suffix}"
    shutil.move(str(target), str(archive_path))
    return archive_path


def copy_caliscope_export_to_pose2sim(source_path: Path, project_dir: Path) -> tuple[Path, Path | None]:
    calibration_dir = assert_under_workspace(project_dir / "calibration")
    calibration_dir.mkdir(parents=True, exist_ok=True)
    archived_path = archive_existing_caliscope_calibration(calibration_dir)
    target_path = calibration_dir / POSE2SIM_CALISCOPE_NAME
    shutil.copy2(source_path, target_path)
    os.utime(target_path, None)
    return target_path, archived_path


def launch_caliscope_for_project(project_dir: Path, python_path: Path = SPORTS3D_PYTHON) -> subprocess.Popen:
    workspace_dir = ensure_caliscope_workspace(project_dir)
    command = [
        str(python_path),
        "-m",
        "pose2sim_pipeline_gui.caliscope_launcher",
        "--workspace",
        str(workspace_dir),
    ]
    try:
        return subprocess.Popen(
            command,
            cwd=str(WORKSPACE_ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        exe_path = python_path.parent / "Scripts" / "caliscope.exe"
        if not exe_path.exists():
            exe_path = python_path.parent / "caliscope.exe"
        if not exe_path.exists():
            raise RuntimeError("当前环境缺少 Caliscope 图形界面组件，请点击修复后重试。")
        seed_caliscope_recent_project(workspace_dir)
        return subprocess.Popen([str(exe_path)], cwd=str(workspace_dir), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def seed_caliscope_recent_project(workspace_dir: Path) -> None:
    try:
        import rtoml
        from caliscope import APP_SETTINGS_PATH

        APP_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        settings = rtoml.load(APP_SETTINGS_PATH) if APP_SETTINGS_PATH.exists() else {}
        recent = [str(path) for path in settings.get("recent_projects", [])]
        workspace_text = str(workspace_dir)
        recent = [path for path in recent if path != workspace_text]
        recent.append(workspace_text)
        settings["recent_projects"] = recent[-10:]
        settings["last_project_parent"] = str(workspace_dir.parent)
        settings.setdefault("force_cpu_rendering", False)
        with APP_SETTINGS_PATH.open("w", encoding="utf-8") as handle:
            rtoml.dump(settings, handle)
    except Exception:
        return


def install_caliscope_gui(python_path: Path = SPORTS3D_PYTHON) -> subprocess.Popen:
    return subprocess.Popen(
        [
            str(python_path),
            "-m",
            "pip",
            "install",
            "--upgrade",
            "--upgrade-strategy",
            "only-if-needed",
            "caliscope[gui]",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
