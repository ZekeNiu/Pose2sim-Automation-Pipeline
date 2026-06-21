from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from pose2sim_pipeline_gui.models import PipelineSettings
from pose2sim_pipeline_gui.paths import PROJECTS_DIR
from pose2sim_pipeline_gui.workspace import ProjectWorkspace


def test_workspace_protects_existing_config_and_backs_up() -> None:
    workspace = ProjectWorkspace("_test_workspace_protection")
    shutil.rmtree(workspace.project_dir, ignore_errors=True)
    try:
        workspace.create()
        (workspace.project_dir / "Config.toml").write_text("[project]\nmulti_person=false\n", encoding="utf-8")

        with pytest.raises(FileExistsError):
            workspace.write_config(PipelineSettings(project_name=workspace.name), overwrite=False)

        workspace.write_config(PipelineSettings(project_name=workspace.name), overwrite=True, backup=True)

        assert (workspace.project_dir / "Config.toml").exists()
        assert list(workspace.project_dir.glob("Config.backup_*.toml"))
    finally:
        shutil.rmtree(workspace.project_dir, ignore_errors=True)
        shutil.rmtree(workspace.output_dir, ignore_errors=True)


def test_workspace_imports_calibration_images_without_ffmpeg(tmp_path: Path) -> None:
    workspace = ProjectWorkspace("_test_workspace_images")
    shutil.rmtree(workspace.project_dir, ignore_errors=True)
    source = tmp_path / "calib.png"
    source.write_bytes(b"fake image bytes")
    try:
        outputs = workspace.import_extrinsics([source])

        assert outputs[0].suffix == ".png"
        assert outputs[0].exists()
        assert workspace.calibration_extension("extrinsics") == "png"
    finally:
        shutil.rmtree(workspace.project_dir, ignore_errors=True)
        shutil.rmtree(workspace.output_dir, ignore_errors=True)


def test_intrinsics_calibration_extension_prefers_images() -> None:
    workspace = ProjectWorkspace("_test_workspace_intrinsics_extension")
    shutil.rmtree(workspace.project_dir, ignore_errors=True)
    try:
        cam_dir = workspace.project_dir / "calibration" / "intrinsics" / "cam01"
        cam_dir.mkdir(parents=True, exist_ok=True)
        (cam_dir / "cam01_intrinsics.mp4").write_bytes(b"video")
        (cam_dir / "cam01_intrinsics_00000.png").write_bytes(b"image")

        assert workspace.calibration_extension("intrinsics") == "png"
    finally:
        shutil.rmtree(workspace.project_dir, ignore_errors=True)
        shutil.rmtree(workspace.output_dir, ignore_errors=True)


def test_prepare_intrinsics_image_frames_keeps_video_and_reports_counts(monkeypatch) -> None:
    workspace = ProjectWorkspace("_test_workspace_prepare_intrinsics")
    shutil.rmtree(workspace.project_dir, ignore_errors=True)
    try:
        cam_dir = workspace.project_dir / "calibration" / "intrinsics" / "cam01"
        cam_dir.mkdir(parents=True, exist_ok=True)
        video_path = cam_dir / "cam01_intrinsics.mp4"
        video_path.write_bytes(b"video")

        def fake_extract(video_file: Path, output_dir: Path, *, extract_every_N_sec: float, overwrite: bool):
            frame = output_dir / "cam01_intrinsics_00000.png"
            frame.write_bytes(b"image")
            return [frame]

        monkeypatch.setattr(
            "pose2sim_pipeline_gui.workspace.pose2sim_intrinsics_video_extraction_bug_present",
            lambda: True,
        )
        monkeypatch.setattr("pose2sim_pipeline_gui.workspace.extract_calibration_video_frames", fake_extract)

        prepared = workspace.prepare_intrinsics_image_frames()

        assert prepared == {"cam01": 1}
        assert video_path.exists()
        assert (cam_dir / "cam01_intrinsics_00000.png").exists()
    finally:
        shutil.rmtree(workspace.project_dir, ignore_errors=True)
        shutil.rmtree(workspace.output_dir, ignore_errors=True)


def test_workspace_imports_external_calibration_files(tmp_path: Path) -> None:
    workspace = ProjectWorkspace("_test_workspace_external_calibration")
    shutil.rmtree(workspace.project_dir, ignore_errors=True)
    source = tmp_path / "capture.qca.txt"
    source.write_text("calibration", encoding="utf-8")
    try:
        outputs = workspace.import_external_calibration([source])

        assert outputs == [workspace.project_dir / "calibration" / "capture.qca.txt"]
        assert outputs[0].read_text(encoding="utf-8") == "calibration"
    finally:
        shutil.rmtree(workspace.project_dir, ignore_errors=True)
        shutil.rmtree(workspace.output_dir, ignore_errors=True)


def test_clear_analysis_results_preserves_inputs_and_config() -> None:
    workspace = ProjectWorkspace("_test_workspace_clear_analysis")
    shutil.rmtree(workspace.project_dir, ignore_errors=True)
    shutil.rmtree(workspace.output_dir, ignore_errors=True)
    try:
        workspace.create()
        (workspace.project_dir / "Config.toml").write_text("[project]\n", encoding="utf-8")
        (workspace.project_dir / "videos" / "cam01.mp4").write_bytes(b"video")
        (workspace.project_dir / "calibration" / "extrinsics" / "cam01.mp4").write_bytes(b"extrinsics")
        (workspace.project_dir / "calibration" / "Calib_scene.toml").write_text("calib", encoding="utf-8")
        for dirname in ["pose", "pose-sync", "pose-associated", "pose-3d", "kinematics"]:
            folder = workspace.project_dir / dirname
            folder.mkdir(parents=True, exist_ok=True)
            (folder / "partial.txt").write_text("partial", encoding="utf-8")
        (workspace.project_dir / "logs.txt").write_text("old log", encoding="utf-8")
        (workspace.output_dir / "reports").mkdir(parents=True, exist_ok=True)
        (workspace.output_dir / "reports" / "old.html").write_text("old", encoding="utf-8")

        removed = workspace.clear_analysis_results()

        assert removed
        for dirname in ["pose", "pose-sync", "pose-associated", "pose-3d", "kinematics"]:
            assert not (workspace.project_dir / dirname).exists()
        assert not (workspace.project_dir / "logs.txt").exists()
        assert not workspace.output_dir.exists()
        assert (workspace.project_dir / "Config.toml").exists()
        assert (workspace.project_dir / "videos" / "cam01.mp4").exists()
        assert (workspace.project_dir / "calibration" / "extrinsics" / "cam01.mp4").exists()
        assert (workspace.project_dir / "calibration" / "Calib_scene.toml").exists()
    finally:
        shutil.rmtree(workspace.project_dir, ignore_errors=True)
        shutil.rmtree(workspace.output_dir, ignore_errors=True)


def test_apply_settings_to_config_only_backs_up_when_changed() -> None:
    workspace = ProjectWorkspace("_test_workspace_apply_config")
    shutil.rmtree(workspace.project_dir, ignore_errors=True)
    try:
        settings = PipelineSettings(project_name=workspace.name, participant_height_m=1.75)
        first = workspace.apply_settings_to_config(settings)
        second = workspace.apply_settings_to_config(settings)
        changed = workspace.apply_settings_to_config(PipelineSettings(project_name=workspace.name, participant_height_m=1.80))

        assert first.changed is True
        assert second.changed is False
        assert changed.changed is True
        assert changed.backup_path is not None
        assert changed.backup_path.exists()
    finally:
        shutil.rmtree(workspace.project_dir, ignore_errors=True)
        shutil.rmtree(workspace.output_dir, ignore_errors=True)


def test_preview_settings_to_config_does_not_write_or_backup() -> None:
    workspace = ProjectWorkspace("_test_workspace_preview_config")
    shutil.rmtree(workspace.project_dir, ignore_errors=True)
    try:
        workspace.create()
        original = "[project]\nparticipant_height='auto'\n"
        (workspace.project_dir / "Config.toml").write_text(original, encoding="utf-8")

        preview = workspace.preview_settings_to_config(PipelineSettings(project_name=workspace.name, participant_height_m=1.80))

        assert preview.changed is True
        assert preview.backup_required is True
        assert "participant_height = 1.8" in preview.merged_text
        assert (workspace.project_dir / "Config.toml").read_text(encoding="utf-8") == original
        assert not list(workspace.project_dir.glob("Config.backup_*.toml"))
    finally:
        shutil.rmtree(workspace.project_dir, ignore_errors=True)
        shutil.rmtree(workspace.output_dir, ignore_errors=True)
