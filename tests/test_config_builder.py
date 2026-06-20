from __future__ import annotations

from pathlib import Path

import pytest

from pose2sim_pipeline_gui.config_builder import build_config_dict, parse_scene_points
from pose2sim_pipeline_gui.models import PipelineSettings


def test_build_config_defaults_for_single_person_phone_workflow() -> None:
    settings = PipelineSettings(project_name="demo", participant_height_m=1.75, sync_times_seconds=[1.0, 1.2])
    config = build_config_dict(Path("D:/Application/Biomechanics/Pose2sim_Pipeline/projects/demo"), settings)

    assert config["project"]["multi_person"] is False
    assert config["project"]["participant_height"] == 1.75
    assert config["pose"]["pose_model"] == "Body_with_feet"
    assert config["pose"]["display_detection"] is False
    assert config["pose"]["parallel_workers_pose"] == "auto"
    assert config["pose"]["save_video"] == "to_video"
    assert config["synchronization"]["approx_time_maxspeed"] == [1.0, 1.2]
    assert config["calibration"]["calculate"]["extrinsics"]["extrinsics_method"] == "scene"
    assert config["kinematics"]["use_augmentation"] is True


def test_board_calibration_switches_extrinsics_method() -> None:
    settings = PipelineSettings(project_name="demo", calibration_mode="board")
    config = build_config_dict(Path("D:/Application/Biomechanics/Pose2sim_Pipeline/projects/demo"), settings)
    assert config["calibration"]["calculate"]["extrinsics"]["extrinsics_method"] == "board"


def test_parse_scene_points_rejects_short_or_bad_values() -> None:
    with pytest.raises(ValueError):
        parse_scene_points("[[0, 0, 0]]")
    with pytest.raises(ValueError):
        parse_scene_points("[[0, 0]]")

