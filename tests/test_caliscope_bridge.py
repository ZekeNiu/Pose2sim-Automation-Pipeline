from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest
import toml

from pose2sim_pipeline_gui.caliscope_bridge import (
    CALISCOPE_EXPORT_NAME,
    find_caliscope_export,
    launch_caliscope_for_project,
    prepare_caliscope_workspace,
    validate_caliscope_export,
)
from pose2sim_pipeline_gui.models import PipelineSettings
from pose2sim_pipeline_gui.workspace import ProjectWorkspace


def _valid_caliscope_data(camera_count: int = 2) -> dict:
    data = {}
    for index in range(camera_count):
        data[f"cam_{index}"] = {
            "name": f"cam_{index}",
            "size": [1920, 1080],
            "matrix": [[1000.0, 0.0, 960.0], [0.0, 1000.0, 540.0], [0.0, 0.0, 1.0]],
            "distortions": [0.0, 0.0, 0.0, 0.0, 0.0],
            "rotation": [0.0, 0.0, 0.0],
            "translation": [float(index), 0.0, 0.0],
            "fisheye": False,
        }
    data["metadata"] = {"adjusted": False, "error": 0.0}
    return data


def _write_caliscope_export(path: Path, camera_count: int = 2) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(toml.dumps(_valid_caliscope_data(camera_count)), encoding="utf-8")


def _write_trial_video(project_dir: Path, camera_label: str) -> Path:
    path = project_dir / "videos" / f"{camera_label}.mp4"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(f"trial {camera_label}".encode("utf-8"))
    return path


def _write_intrinsic_video(project_dir: Path, camera_label: str) -> Path:
    path = project_dir / "calibration" / "intrinsics" / camera_label / f"{camera_label}_intrinsics.mp4"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(f"intrinsic {camera_label}".encode("utf-8"))
    return path


def _write_extrinsic_file(project_dir: Path, camera_label: str, suffix: str = ".mp4") -> Path:
    path = project_dir / "calibration" / "extrinsics" / f"{camera_label}{suffix}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(f"extrinsic {camera_label}".encode("utf-8"))
    return path


def _clean_workspace(workspace: ProjectWorkspace) -> None:
    shutil.rmtree(workspace.project_dir, ignore_errors=True)
    shutil.rmtree(workspace.output_dir, ignore_errors=True)


def test_find_caliscope_export_uses_newest_result(tmp_path: Path) -> None:
    old_result = tmp_path / "old" / CALISCOPE_EXPORT_NAME
    new_result = tmp_path / "new" / CALISCOPE_EXPORT_NAME
    _write_caliscope_export(old_result)
    _write_caliscope_export(new_result)
    os.utime(old_result, (1, 1))
    os.utime(new_result, (2, 2))

    assert find_caliscope_export(tmp_path) == new_result


def test_find_caliscope_export_reports_user_action_when_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="没有找到 Caliscope 校准结果"):
        find_caliscope_export(tmp_path)


def test_validate_caliscope_export_rejects_missing_fields(tmp_path: Path) -> None:
    source = tmp_path / CALISCOPE_EXPORT_NAME
    source.write_text("[cam_0]\nsize=[1920,1080]\n", encoding="utf-8")

    with pytest.raises(ValueError, match="校准结果不完整"):
        validate_caliscope_export(source)


def test_validate_caliscope_export_checks_camera_count(tmp_path: Path) -> None:
    source = tmp_path / CALISCOPE_EXPORT_NAME
    _write_caliscope_export(source, camera_count=2)

    with pytest.raises(ValueError, match="相机数量是 2，当前项目视频数量是 3"):
        validate_caliscope_export(source, expected_camera_count=3)


def test_prepare_caliscope_workspace_maps_project_videos() -> None:
    workspace = ProjectWorkspace("_test_workspace_prepare_caliscope")
    _clean_workspace(workspace)
    try:
        workspace.create()
        _write_trial_video(workspace.project_dir, "cam01")
        _write_trial_video(workspace.project_dir, "cam02")
        _write_intrinsic_video(workspace.project_dir, "cam01")
        _write_intrinsic_video(workspace.project_dir, "cam02")
        _write_extrinsic_file(workspace.project_dir, "cam01")
        _write_extrinsic_file(workspace.project_dir, "cam02")
        stale_video = workspace.caliscope_workspace() / "calibration" / "extrinsic" / "cam_9.mp4"
        stale_video.parent.mkdir(parents=True, exist_ok=True)
        stale_video.write_bytes(b"stale")

        result = prepare_caliscope_workspace(workspace.project_dir)

        assert result.camera_count == 2
        assert [camera.camera_label for camera in result.cameras] == ["cam01", "cam02"]
        assert (workspace.caliscope_workspace() / "calibration" / "intrinsic" / "cam_0.mp4").read_bytes() == b"intrinsic cam01"
        assert (workspace.caliscope_workspace() / "calibration" / "extrinsic" / "cam_0.mp4").read_bytes() == b"extrinsic cam01"
        assert (workspace.caliscope_workspace() / "calibration" / "intrinsic" / "cam_1.mp4").read_bytes() == b"intrinsic cam02"
        assert (workspace.caliscope_workspace() / "calibration" / "extrinsic" / "cam_1.mp4").read_bytes() == b"extrinsic cam02"
        assert not stale_video.exists()
    finally:
        _clean_workspace(workspace)


def test_prepare_caliscope_workspace_reports_missing_intrinsics() -> None:
    workspace = ProjectWorkspace("_test_workspace_prepare_missing_intrinsics")
    _clean_workspace(workspace)
    try:
        workspace.create()
        _write_trial_video(workspace.project_dir, "cam01")
        _write_trial_video(workspace.project_dir, "cam02")
        _write_intrinsic_video(workspace.project_dir, "cam01")
        _write_extrinsic_file(workspace.project_dir, "cam01")
        _write_extrinsic_file(workspace.project_dir, "cam02")
        existing_video = workspace.caliscope_workspace() / "calibration" / "intrinsic" / "cam_0.mp4"
        existing_video.parent.mkdir(parents=True, exist_ok=True)
        existing_video.write_bytes(b"existing")

        with pytest.raises(ValueError, match="缺少内参视频"):
            prepare_caliscope_workspace(workspace.project_dir)
        assert existing_video.read_bytes() == b"existing"
    finally:
        _clean_workspace(workspace)


def test_prepare_caliscope_workspace_reports_missing_extrinsics() -> None:
    workspace = ProjectWorkspace("_test_workspace_prepare_missing_extrinsics")
    _clean_workspace(workspace)
    try:
        workspace.create()
        _write_trial_video(workspace.project_dir, "cam01")
        _write_trial_video(workspace.project_dir, "cam02")
        _write_intrinsic_video(workspace.project_dir, "cam01")
        _write_intrinsic_video(workspace.project_dir, "cam02")
        _write_extrinsic_file(workspace.project_dir, "cam01")

        with pytest.raises(ValueError, match="缺少外参视频"):
            prepare_caliscope_workspace(workspace.project_dir)
    finally:
        _clean_workspace(workspace)


def test_prepare_caliscope_workspace_rejects_image_only_extrinsics() -> None:
    workspace = ProjectWorkspace("_test_workspace_prepare_image_extrinsics")
    _clean_workspace(workspace)
    try:
        workspace.create()
        _write_trial_video(workspace.project_dir, "cam01")
        _write_trial_video(workspace.project_dir, "cam02")
        _write_intrinsic_video(workspace.project_dir, "cam01")
        _write_intrinsic_video(workspace.project_dir, "cam02")
        _write_extrinsic_file(workspace.project_dir, "cam01", ".png")
        _write_extrinsic_file(workspace.project_dir, "cam02", ".jpg")

        with pytest.raises(ValueError, match="Caliscope 需要重新导入外参视频"):
            prepare_caliscope_workspace(workspace.project_dir)
    finally:
        _clean_workspace(workspace)


def test_prepare_caliscope_workspace_keeps_saved_caliscope_results() -> None:
    workspace = ProjectWorkspace("_test_workspace_prepare_preserves_results")
    _clean_workspace(workspace)
    try:
        workspace.create()
        _write_trial_video(workspace.project_dir, "cam01")
        _write_trial_video(workspace.project_dir, "cam02")
        _write_intrinsic_video(workspace.project_dir, "cam01")
        _write_intrinsic_video(workspace.project_dir, "cam02")
        _write_extrinsic_file(workspace.project_dir, "cam01")
        _write_extrinsic_file(workspace.project_dir, "cam02")
        export = workspace.caliscope_workspace() / CALISCOPE_EXPORT_NAME
        _write_caliscope_export(export)

        prepare_caliscope_workspace(workspace.project_dir)
        prepare_caliscope_workspace(workspace.project_dir)

        assert export.exists()
        assert toml.load(export)["cam_0"]["name"] == "cam_0"
    finally:
        _clean_workspace(workspace)


def test_prepare_caliscope_workspace_checks_trial_video_count() -> None:
    workspace = ProjectWorkspace("_test_workspace_prepare_trial_count")
    _clean_workspace(workspace)
    try:
        workspace.create()
        _write_trial_video(workspace.project_dir, "cam01")
        _write_trial_video(workspace.project_dir, "cam02")
        _write_trial_video(workspace.project_dir, "cam03")
        _write_intrinsic_video(workspace.project_dir, "cam01")
        _write_intrinsic_video(workspace.project_dir, "cam02")
        _write_extrinsic_file(workspace.project_dir, "cam01")
        _write_extrinsic_file(workspace.project_dir, "cam02")

        with pytest.raises(ValueError, match="当前项目测试视频数量是 3"):
            prepare_caliscope_workspace(workspace.project_dir)
    finally:
        _clean_workspace(workspace)


def test_workspace_imports_caliscope_result_and_updates_config() -> None:
    workspace = ProjectWorkspace("_test_workspace_caliscope")
    shutil.rmtree(workspace.project_dir, ignore_errors=True)
    shutil.rmtree(workspace.output_dir, ignore_errors=True)
    try:
        workspace.create()
        (workspace.project_dir / "videos" / "cam01.mp4").write_bytes(b"video")
        (workspace.project_dir / "videos" / "cam02.mp4").write_bytes(b"video")
        (workspace.project_dir / "calibration" / "Calib_caliscope.toml").write_text("old", encoding="utf-8")
        (workspace.project_dir / "Config.toml").write_text(
            "[project]\nmulti_person=false\n[calibration]\ncalibration_type='calculate'\n[calibration.convert]\ncustom_field=true\n",
            encoding="utf-8",
        )
        _write_caliscope_export(workspace.caliscope_workspace() / CALISCOPE_EXPORT_NAME, camera_count=2)

        result = workspace.import_caliscope_calibration(PipelineSettings(project_name=workspace.name))
        config = toml.load(result.config_path)

        assert result.camera_count == 2
        assert result.target_path == workspace.project_dir / "calibration" / "Calib_caliscope.toml"
        assert result.target_path.exists()
        assert result.archived_calibration_path is not None
        assert result.archived_calibration_path.exists()
        assert result.config_changed is True
        assert result.config_backup_path is not None
        assert config["calibration"]["calibration_type"] == "convert"
        assert config["calibration"]["convert"]["convert_from"] == "caliscope"
        assert config["calibration"]["convert"]["custom_field"] is True
    finally:
        shutil.rmtree(workspace.project_dir, ignore_errors=True)
        shutil.rmtree(workspace.output_dir, ignore_errors=True)


def test_workspace_detects_inputs_newer_than_mot_outputs() -> None:
    workspace = ProjectWorkspace("_test_workspace_stale_outputs")
    shutil.rmtree(workspace.project_dir, ignore_errors=True)
    shutil.rmtree(workspace.output_dir, ignore_errors=True)
    try:
        workspace.create()
        kinematics = workspace.project_dir / "kinematics"
        kinematics.mkdir()
        mot = kinematics / "trial.mot"
        mot.write_text("mot", encoding="utf-8")
        config = workspace.project_dir / "Config.toml"
        config.write_text("[project]\n", encoding="utf-8")
        os.utime(mot, (10, 10))
        os.utime(config, (20, 20))

        assert workspace.analysis_inputs_newer_than_outputs() is True

        os.utime(config, (5, 5))
        assert workspace.analysis_inputs_newer_than_outputs() is False
    finally:
        shutil.rmtree(workspace.project_dir, ignore_errors=True)
        shutil.rmtree(workspace.output_dir, ignore_errors=True)


def test_launch_caliscope_uses_bridge_module(monkeypatch) -> None:
    workspace = ProjectWorkspace("_test_workspace_launch_caliscope")
    shutil.rmtree(workspace.project_dir, ignore_errors=True)
    calls: list[list[str]] = []

    class DummyProcess:
        pass

    def fake_popen(command, **_kwargs):
        calls.append([str(part) for part in command])
        return DummyProcess()

    monkeypatch.setattr("pose2sim_pipeline_gui.caliscope_bridge.subprocess.Popen", fake_popen)
    try:
        workspace.create()
        process = launch_caliscope_for_project(workspace.project_dir, python_path=Path("python.exe"))

        assert isinstance(process, DummyProcess)
        assert calls[0][1:4] == ["-m", "pose2sim_pipeline_gui.caliscope_launcher", "--workspace"]
        assert calls[0][4].endswith("caliscope_workspace")
    finally:
        shutil.rmtree(workspace.project_dir, ignore_errors=True)
        shutil.rmtree(workspace.output_dir, ignore_errors=True)


def test_launch_caliscope_falls_back_to_exe(monkeypatch, tmp_path: Path) -> None:
    workspace = ProjectWorkspace("_test_workspace_launch_caliscope_fallback")
    shutil.rmtree(workspace.project_dir, ignore_errors=True)
    env_dir = tmp_path / "env"
    scripts_dir = env_dir / "Scripts"
    scripts_dir.mkdir(parents=True)
    (scripts_dir / "caliscope.exe").write_text("exe", encoding="utf-8")
    calls: list[list[str]] = []

    class DummyProcess:
        pass

    def fake_popen(command, **_kwargs):
        calls.append([str(part) for part in command])
        if len(calls) == 1:
            raise OSError("bridge failed")
        return DummyProcess()

    monkeypatch.setattr("pose2sim_pipeline_gui.caliscope_bridge.subprocess.Popen", fake_popen)
    try:
        workspace.create()
        process = launch_caliscope_for_project(workspace.project_dir, python_path=env_dir / "python.exe")

        assert isinstance(process, DummyProcess)
        assert calls[1][0].endswith("caliscope.exe")
    finally:
        shutil.rmtree(workspace.project_dir, ignore_errors=True)
        shutil.rmtree(workspace.output_dir, ignore_errors=True)
