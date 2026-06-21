from __future__ import annotations

from pose2sim_pipeline_gui.pipeline_cli import should_run_marker_augmentation


def test_should_run_marker_augmentation_respects_config() -> None:
    assert should_run_marker_augmentation([{"kinematics": {"use_augmentation": False}}]) is False
    assert should_run_marker_augmentation([{"kinematics": {"use_augmentation": True}}]) is True
    assert should_run_marker_augmentation([{}]) is True
