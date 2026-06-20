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
    assert config["synchronization"]["time_range_around_maxspeed"] == 2.0
    assert config["calibration"]["calculate"]["extrinsics"]["extrinsics_method"] == "scene"
    assert config["markerAugmentation"]["feet_on_floor"] is False
    assert config["kinematics"]["use_augmentation"] is True
    assert config["kinematics"]["right_left_symmetry"] is True


def test_build_config_writes_exposed_gui_parameters() -> None:
    settings = PipelineSettings(
        project_name="demo",
        pose_model="Whole_body_wrist",
        speed_preset="accurate",
        save_overlay_video=False,
        feet_on_floor=True,
        right_left_symmetry=False,
        extrinsics_board_position="vertical",
        intrinsics_square_size_mm=32.0,
        intrinsics_extension="jpg",
        extrinsics_square_size_mm=45.0,
        extrinsics_extension="png",
        sync_search_range_seconds=3.5,
        filter_cutoff_hz=8.0,
    )
    config = build_config_dict(Path("D:/Application/Biomechanics/Pose2sim_Pipeline/projects/demo"), settings)

    assert config["pose"]["pose_model"] == "Whole_body_wrist"
    assert config["pose"]["mode"] == "performance"
    assert config["pose"]["det_frequency"] == 2
    assert config["pose"]["save_video"] == "none"
    assert config["calibration"]["calculate"]["intrinsics"]["intrinsics_extension"] == "jpg"
    assert config["calibration"]["calculate"]["intrinsics"]["intrinsics_square_size"] == 32.0
    assert config["calibration"]["calculate"]["extrinsics"]["extrinsics_extension"] == "png"
    assert config["calibration"]["calculate"]["extrinsics"]["board"]["extrinsics_square_size"] == 45.0
    assert config["calibration"]["calculate"]["extrinsics"]["board"]["board_position"] == "vertical"
    assert config["synchronization"]["time_range_around_maxspeed"] == 3.5
    assert config["markerAugmentation"]["feet_on_floor"] is True
    assert config["kinematics"]["right_left_symmetry"] is False
    assert config["filtering"]["butterworth"]["cut_off_frequency"] == 8.0


def test_board_calibration_switches_extrinsics_method() -> None:
    settings = PipelineSettings(project_name="demo", calibration_mode="board", scene_points_text="not a scene point list")
    config = build_config_dict(Path("D:/Application/Biomechanics/Pose2sim_Pipeline/projects/demo"), settings)
    assert config["calibration"]["calculate"]["extrinsics"]["extrinsics_method"] == "board"


def test_multi_person_config_writes_participant_lists() -> None:
    settings = PipelineSettings(
        project_name="demo",
        multi_person=True,
        participant_heights_m=[1.80, 1.65],
        participant_masses_kg=[82.0, 60.0],
    )
    config = build_config_dict(Path("D:/Application/Biomechanics/Pose2sim_Pipeline/projects/demo"), settings)

    assert config["project"]["multi_person"] is True
    assert config["project"]["participant_height"] == [1.8, 1.65]
    assert config["project"]["participant_mass"] == [82.0, 60.0]


def test_parse_scene_points_accepts_table_rows() -> None:
    text = """点编号,X,Y,Z,现场说明
P1,0,0,0,原点
P2,1,0,0,前方1米
P3,0,1,0,左方1米
P4,0,0,1,上方1米
P5,1,1,0,左前
P6,1,0,1,前上
"""
    assert parse_scene_points(text) == [
        [0.0, 0.0, 0.0],
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0],
        [1.0, 1.0, 0.0],
        [1.0, 0.0, 1.0],
    ]


def test_parse_scene_points_rejects_short_or_bad_values() -> None:
    with pytest.raises(ValueError):
        parse_scene_points("[[0, 0, 0]]")
    with pytest.raises(ValueError):
        parse_scene_points("[[0, 0]]")


def test_gui_labels_map_to_pose2sim_internal_values() -> None:
    from pose2sim_pipeline_gui.app import BOARD_POSITION_OPTIONS, CALIBRATION_MODE_OPTIONS, SPEED_PRESET_OPTIONS, STEP_TABS

    assert STEP_TABS == ["环境", "项目", "校准", "视频", "参数", "运行"]
    assert CALIBRATION_MODE_OPTIONS["外参：场景点（推荐，精度更稳）"] == "scene"
    assert CALIBRATION_MODE_OPTIONS["外参：棋盘格（更简单，要求所有相机清楚看到大棋盘格）"] == "board"
    assert BOARD_POSITION_OPTIONS["水平放置（地面/地垫）"] == "horizontal"
    assert BOARD_POSITION_OPTIONS["垂直放置（墙面/支架）"] == "vertical"
    assert SPEED_PRESET_OPTIONS["更准（performance，较慢）"] == "accurate"
