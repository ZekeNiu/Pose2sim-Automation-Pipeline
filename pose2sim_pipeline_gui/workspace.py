from __future__ import annotations

import shutil
from pathlib import Path

from .config_builder import write_config
from .models import PipelineSettings
from .paths import PROJECTS_DIR, assert_under_workspace, ensure_workspace, output_dir, project_dir, sanitize_project_name
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

    def write_config(self, settings: PipelineSettings) -> Path:
        self.create()
        return write_config(self.project_dir, settings)

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
            output = self.project_dir / "calibration" / "extrinsics" / f"{cam}.mp4"
            normalize_video(source, output)
            outputs.append(output)
        return outputs


def list_projects() -> list[str]:
    ensure_workspace()
    return sorted(p.name for p in PROJECTS_DIR.iterdir() if p.is_dir() and p.name != ".gitkeep")
