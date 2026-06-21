from __future__ import annotations

from pathlib import Path

from pose2sim_pipeline_gui.pipeline_cli import normalize_config_dicts_for_runtime, should_run_marker_augmentation


def test_should_run_marker_augmentation_respects_config() -> None:
    assert should_run_marker_augmentation([{"kinematics": {"use_augmentation": False}}]) is False
    assert should_run_marker_augmentation([{"kinematics": {"use_augmentation": True}}]) is True
    assert should_run_marker_augmentation([{}]) is True


def test_runtime_config_normalizes_old_trimmed_extrema_units(monkeypatch) -> None:
    monkeypatch.setattr("pose2sim_pipeline_gui.pipeline_cli.pose2sim_uses_percent_trimmed_extrema", lambda: True)
    config_dicts = [{"kinematics": {"trimmed_extrema_percent": 0.5}}, {"kinematics": {"trimmed_extrema_percent": 40}}]

    normalize_config_dicts_for_runtime(config_dicts)

    assert config_dicts[0]["kinematics"]["trimmed_extrema_percent"] == 50.0
    assert config_dicts[1]["kinematics"]["trimmed_extrema_percent"] == 40


def test_runtime_config_switches_intrinsics_video_extension_to_png(tmp_path: Path) -> None:
    cam_dir = tmp_path / "calibration" / "intrinsics" / "cam01"
    cam_dir.mkdir(parents=True)
    (cam_dir / "cam01_intrinsics.mp4").write_bytes(b"video")
    (cam_dir / "cam01_intrinsics_00000.png").write_bytes(b"image")
    config_dicts = [
        {"calibration": {"calculate": {"intrinsics": {"intrinsics_extension": "mp4"}}}},
    ]

    normalize_config_dicts_for_runtime(config_dicts, tmp_path)

    assert config_dicts[0]["calibration"]["calculate"]["intrinsics"]["intrinsics_extension"] == "png"
