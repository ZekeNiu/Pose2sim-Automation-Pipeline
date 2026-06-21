from __future__ import annotations

from pathlib import Path

import pytest

from pose2sim_pipeline_gui.config_builder import build_config_dict, parse_scene_points
from pose2sim_pipeline_gui.config_adapter import merged_config, settings_from_config
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
    assert config["pose"]["tracking_mode"] == "sports2d"
    assert config["synchronization"]["synchronization_gui"] is False
    assert config["synchronization"]["approx_time_maxspeed"] == [1.0, 1.2]
    assert config["synchronization"]["time_range_around_maxspeed"] == 2.0
    assert config["calibration"]["calculate"]["extrinsics"]["extrinsics_method"] == "scene"
    assert config["personAssociation"]["single_person"]["tracked_keypoint"] == "Neck"
    assert config["markerAugmentation"]["feet_on_floor"] is False
    assert config["kinematics"]["use_augmentation"] is True
    assert config["kinematics"]["right_left_symmetry"] is True
    assert config["kinematics"]["filter_ik"] is False
    assert config["kinematics"]["ik_filter_type"] == "acc_minimizing"


def test_build_config_writes_new_pose2sim_scaling_defaults(monkeypatch) -> None:
    monkeypatch.setattr("pose2sim_pipeline_gui.config_builder.pose2sim_uses_percent_trimmed_extrema", lambda: True)
    config = build_config_dict(Path("D:/Application/Biomechanics/Pose2sim_Pipeline/projects/demo"), PipelineSettings(project_name="demo"))

    assert config["kinematics"]["large_hip_knee_angles"] == 90.0
    assert config["kinematics"]["trimmed_extrema_percent"] == 50.0


def test_build_config_keeps_old_trimmed_extrema_units_for_pose2sim_01043(monkeypatch) -> None:
    monkeypatch.setattr("pose2sim_pipeline_gui.config_builder.pose2sim_uses_percent_trimmed_extrema", lambda: False)
    config = build_config_dict(Path("D:/Application/Biomechanics/Pose2sim_Pipeline/projects/demo"), PipelineSettings(project_name="demo"))

    assert config["kinematics"]["large_hip_knee_angles"] == 90.0
    assert config["kinematics"]["trimmed_extrema_percent"] == 0.5


def test_build_config_writes_exposed_gui_parameters(monkeypatch) -> None:
    monkeypatch.setattr("pose2sim_pipeline_gui.config_builder.pose2sim_uses_percent_trimmed_extrema", lambda: True)
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
        tracking_mode="sports2d",
        tracked_keypoint="Hip",
        manual_sync_selection=True,
        trimmed_extrema_percent=40.0,
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
    assert config["synchronization"]["synchronization_gui"] is True
    assert config["personAssociation"]["single_person"]["tracked_keypoint"] == "Hip"
    assert config["markerAugmentation"]["feet_on_floor"] is True
    assert config["kinematics"]["right_left_symmetry"] is False
    assert config["kinematics"]["trimmed_extrema_percent"] == 40.0
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


def test_external_calibration_format_is_written_and_round_trips() -> None:
    settings = PipelineSettings(project_name="demo", calibration_mode="convert", external_calibration_format="vicon")
    config = build_config_dict(Path("D:/Application/Biomechanics/Pose2sim_Pipeline/projects/demo"), settings)

    assert config["calibration"]["calibration_type"] == "convert"
    assert config["calibration"]["convert"]["convert_from"] == "vicon"

    existing = {
        "project": {"multi_person": False},
        "calibration": {
            "calibration_type": "convert",
            "convert": {
                "convert_from": "qualisys",
                "custom_field": True,
                "vicon": {"manual_path": "keep"},
                "qualisys": {"binning_factor": 2, "manual_value": "keep"},
            },
        },
    }
    converted = settings_from_config("demo", existing)
    assert converted.external_calibration_format == "qualisys"

    merged = merged_config(
        Path("D:/Application/Biomechanics/Pose2sim_Pipeline/projects/demo"),
        existing,
        settings,
    )
    assert merged["calibration"]["convert"]["convert_from"] == "vicon"
    assert merged["calibration"]["convert"]["custom_field"] is True
    assert merged["calibration"]["convert"]["vicon"]["manual_path"] == "keep"
    assert merged["calibration"]["convert"]["qualisys"]["binning_factor"] == 2
    assert merged["calibration"]["convert"]["qualisys"]["manual_value"] == "keep"


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


def test_parse_scene_points_accepts_any_count_from_6_to_15() -> None:
    for count in range(6, 16):
        text = "\n".join(f"P{i},{i},0,0,点{i}" for i in range(1, count + 1))
        assert len(parse_scene_points(text)) == count


def test_parse_scene_points_rejects_short_or_bad_values() -> None:
    five_points = "\n".join(f"P{i},{i},0,0,点{i}" for i in range(1, 6))
    with pytest.raises(ValueError):
        parse_scene_points(five_points)
    with pytest.raises(ValueError):
        parse_scene_points("[[0, 0, 0]]")
    with pytest.raises(ValueError):
        parse_scene_points("[[0, 0]]")


def test_gui_labels_map_to_pose2sim_internal_values() -> None:
    from pose2sim_pipeline_gui.app import (
        BOARD_POSITION_OPTIONS,
        CALIBRATION_MODE_OPTIONS,
        MAX_SCENE_POINTS,
        MIN_SCENE_POINTS,
        SPEED_PRESET_OPTIONS,
        STEP_TABS,
        TARGET_SELECTION_OPTIONS,
        TRACKED_KEYPOINT_OPTIONS,
        parse_float_list,
    )

    assert STEP_TABS == ["环境", "项目", "校准", "视频", "参数", "运行"]
    assert CALIBRATION_MODE_OPTIONS["外参：场景点（推荐，精度更稳）"] == "scene"
    assert CALIBRATION_MODE_OPTIONS["外参：棋盘格（更简单，要求所有相机清楚看到大棋盘格）"] == "board"
    assert BOARD_POSITION_OPTIONS["水平放置（地面/地垫）"] == "horizontal"
    assert BOARD_POSITION_OPTIONS["垂直放置（墙面/支架）"] == "vertical"
    assert MIN_SCENE_POINTS == 6
    assert MAX_SCENE_POINTS == 15
    assert SPEED_PRESET_OPTIONS["更准（performance，较慢）"] == "accurate"
    assert TARGET_SELECTION_OPTIONS["自动跟踪（推荐，单人清晰场景）"] == "auto"
    assert TARGET_SELECTION_OPTIONS["官方手动选人/同步（会弹出 Pose2Sim 英文窗口）"] == "manual_sync"
    assert TRACKED_KEYPOINT_OPTIONS["Hip（下肢动作、躯干遮挡时可试）"] == "Hip"
    assert parse_float_list("1.2，1.4") == [1.2, 1.4]
    assert parse_float_list("1.2, 1.4; 1.6") == [1.2, 1.4, 1.6]
    assert parse_float_list("") == []
    with pytest.raises(ValueError, match="请输入数字"):
        parse_float_list("1.2，错误")


def test_existing_convert_config_round_trips_without_forcing_calculate() -> None:
    existing = {
        "project": {"multi_person": False, "participant_height": "auto", "participant_mass": 70.0, "frame_range": "auto"},
        "pose": {
            "pose_model": "Body_with_feet",
            "mode": "balanced",
            "det_frequency": 4,
            "save_video": "to_video",
            "tracking_mode": "sports2d",
        },
        "calibration": {"calibration_type": "convert", "convert": {"convert_from": "qualisys", "custom_field": True}},
        "synchronization": {
            "approx_time_maxspeed": "auto",
            "time_range_around_maxspeed": 2.0,
            "synchronization_gui": True,
        },
        "personAssociation": {"single_person": {"tracked_keypoint": "Hip"}},
        "kinematics": {"use_augmentation": True, "right_left_symmetry": True, "default_height": 1.7},
    }
    settings = settings_from_config("demo", existing)
    merged = merged_config(Path("D:/Application/Biomechanics/Pose2sim_Pipeline/projects/demo"), existing, settings)

    assert settings.calibration_mode == "convert"
    assert settings.manual_sync_selection is True
    assert settings.tracked_keypoint == "Hip"
    assert merged["calibration"]["calibration_type"] == "convert"
    assert merged["calibration"]["convert"]["custom_field"] is True


def test_existing_old_trimmed_extrema_ratio_is_read_as_percent(monkeypatch) -> None:
    monkeypatch.setattr("pose2sim_pipeline_gui.config_builder.pose2sim_uses_percent_trimmed_extrema", lambda: True)
    existing = {
        "project": {"multi_person": False, "participant_height": "auto", "participant_mass": 70.0, "frame_range": "auto"},
        "pose": {"pose_model": "Body_with_feet", "mode": "balanced", "det_frequency": 4, "save_video": "to_video"},
        "kinematics": {"trimmed_extrema_percent": 0.5, "large_hip_knee_angles": 135.0},
    }

    settings = settings_from_config("demo", existing)
    merged = merged_config(Path("D:/Application/Biomechanics/Pose2sim_Pipeline/projects/demo"), existing, settings)

    assert settings.trimmed_extrema_percent == 50.0
    assert merged["kinematics"]["trimmed_extrema_percent"] == 50.0
    assert merged["kinematics"]["large_hip_knee_angles"] == 135.0
    assert merged["kinematics"]["filter_ik"] is False
    assert merged["kinematics"]["ik_filter_type"] == "acc_minimizing"
    assert merged["filtering"]["filter_ik"] is False


def test_gui_labels_include_lower_body_option() -> None:
    from pose2sim_pipeline_gui.app import POSE_MODEL_OPTIONS

    assert POSE_MODEL_OPTIONS["下肢模式（Pose2Sim 0.10.44+）"] == "Lower_body"
