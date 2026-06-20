from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

import toml

from .config_adapter import ConfigApplyResult, config_text, load_config, merged_config
from .config_builder import write_config
from .models import PipelineSettings
from .paths import PROJECTS_DIR, assert_under_workspace, ensure_workspace, output_dir, project_dir, sanitize_project_name
from .project_state import ProjectStatus, inspect_project
from .video import VideoInfo, inspect_video, normalize_video


VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".m4v", ".webm"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}


class ProjectWorkspace:
    def __init__(self, name: str):
        ensure_workspace()
        self.name = sanitize_project_name(name)
        self.project_dir = project_dir(self.name)
        self.output_dir = output_dir(self.name)

    def create(self) -> None:
        for directory in [
            self.project_dir,
            self.output_dir,
            self.project_dir / "source" / "videos",
            self.project_dir / "source" / "calibration_intrinsics",
            self.project_dir / "source" / "calibration_extrinsics",
            self.project_dir / "videos",
            self.project_dir / "calibration" / "intrinsics",
            self.project_dir / "calibration" / "extrinsics",
        ]:
            assert_under_workspace(directory).mkdir(parents=True, exist_ok=True)

    def status(self) -> ProjectStatus:
        return inspect_project(self.project_dir)

    def backup_config(self) -> Path | None:
        config_path = self.project_dir / "Config.toml"
        if not config_path.exists():
            return None
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.project_dir / f"Config.backup_{stamp}.toml"
        shutil.copy2(config_path, backup_path)
        return backup_path

    def write_config(self, settings: PipelineSettings, overwrite: bool = False, backup: bool = True) -> Path:
        self.create()
        config_path = self.project_dir / "Config.toml"
        if config_path.exists() and not overwrite:
            raise FileExistsError(
                f"{config_path} 已存在。为保护已有项目，GUI 不会自动覆盖。请选择备份并覆盖，或直接按现有 Config 运行。"
            )
        if config_path.exists() and backup:
            self.backup_config()
        return write_config(self.project_dir, settings)

    def apply_settings_to_config(self, settings: PipelineSettings) -> ConfigApplyResult:
        self.create()
        config_path = self.project_dir / "Config.toml"
        if not config_path.exists():
            return ConfigApplyResult(path=write_config(self.project_dir, settings), changed=True)

        existing = load_config(config_path)
        merged = merged_config(self.project_dir, existing, settings)
        if config_text(existing) == config_text(merged):
            return ConfigApplyResult(path=config_path, changed=False)

        backup_path = self.backup_config()
        with config_path.open("w", encoding="utf-8") as handle:
            toml.dump(merged, handle)
        return ConfigApplyResult(path=config_path, changed=True, backup_path=backup_path)

    def calibration_extension(self, kind: str) -> str:
        if kind not in {"intrinsics", "extrinsics"}:
            raise ValueError("kind 必须是 intrinsics 或 extrinsics")
        folder = self.project_dir / "calibration" / kind
        if not folder.exists():
            return "mp4"
        files = sorted(path for path in folder.rglob("*") if path.is_file())
        for path in files:
            suffix = path.suffix.lower().lstrip(".")
            if suffix:
                return suffix
        return "mp4"

    def import_trial_videos(self, files: list[Path]) -> list[VideoInfo]:
        self.create()
        infos: list[VideoInfo] = []
        for index, file_path in enumerate(files, start=1):
            cam = f"cam{index:02d}"
            source = self.project_dir / "source" / "videos" / f"{cam}{file_path.suffix.lower()}"
            shutil.copy2(file_path, source)
            output = self.project_dir / "videos" / f"{cam}.mp4"
            info_before = inspect_video(source)
            info_after = normalize_video(source, output)
            info_after.rotation = info_before.rotation
            infos.append(info_after)
        return infos

    def import_intrinsics(self, files: list[Path]) -> list[Path]:
        self.create()
        outputs: list[Path] = []
        for index, file_path in enumerate(files, start=1):
            cam = f"cam{index:02d}"
            source = self.project_dir / "source" / "calibration_intrinsics" / f"{cam}{file_path.suffix.lower()}"
            shutil.copy2(file_path, source)
            cam_dir = self.project_dir / "calibration" / "intrinsics" / cam
            cam_dir.mkdir(parents=True, exist_ok=True)
            suffix = file_path.suffix.lower()
            if suffix in IMAGE_EXTENSIONS:
                output = cam_dir / f"{cam}_intrinsics{suffix}"
                shutil.copy2(source, output)
            else:
                output = cam_dir / f"{cam}_intrinsics.mp4"
                normalize_video(source, output)
            outputs.append(output)
        return outputs

    def import_extrinsics(self, files: list[Path]) -> list[Path]:
        self.create()
        outputs: list[Path] = []
        for index, file_path in enumerate(files, start=1):
            cam = f"cam{index:02d}"
            source = self.project_dir / "source" / "calibration_extrinsics" / f"{cam}{file_path.suffix.lower()}"
            shutil.copy2(file_path, source)
            suffix = file_path.suffix.lower()
            if suffix in IMAGE_EXTENSIONS:
                output = self.project_dir / "calibration" / "extrinsics" / f"{cam}{suffix}"
                shutil.copy2(source, output)
            else:
                output = self.project_dir / "calibration" / "extrinsics" / f"{cam}.mp4"
                normalize_video(source, output)
            outputs.append(output)
        return outputs


def list_projects() -> list[str]:
    ensure_workspace()
    return sorted(p.name for p in PROJECTS_DIR.iterdir() if p.is_dir() and p.name != ".gitkeep")
