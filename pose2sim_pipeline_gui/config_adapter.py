from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import toml

from .config_builder import build_config_dict
from .models import PipelineSettings


@dataclass(frozen=True)
class ConfigApplyResult:
    path: Path
    changed: bool
    backup_path: Path | None = None


def load_config(path: Path) -> dict[str, Any]:
    return toml.load(path) if path.exists() else {}


def _first_float(value: Any, default: float | None = None) -> float | None:
    if isinstance(value, list):
        return float(value[0]) if value else default
    if value in {None, "", "auto"}:
        return default
    return float(value)


def _float_list(value: Any) -> list[float]:
    if isinstance(value, list):
        return [float(item) for item in value]
    if value in {None, "", "auto"}:
        return []
    return [float(value)]


def _frame_range(value: Any) -> tuple[int | None, int | None]:
    if isinstance(value, list) and len(value) >= 2:
        return int(value[0]), int(value[1])
    return None, None


def _sync_times(value: Any) -> list[float]:
    if isinstance(value, list):
        return [float(item) for item in value]
    return []


def _speed_preset_from_pose(mode: Any) -> str:
    if mode == "lightweight":
        return "fast"
    if mode == "performance":
        return "accurate"
    return "balanced"


def settings_from_config(project_name: str, config: dict[str, Any]) -> PipelineSettings:
    project = config.get("project", {})
    pose = config.get("pose", {})
    synchronization = config.get("synchronization", {})
    calibration = config.get("calibration", {})
    convert = calibration.get("convert", {})
    calculate = calibration.get("calculate", {})
    intrinsics = calculate.get("intrinsics", {})
    extrinsics = calculate.get("extrinsics", {})
    filtering = config.get("filtering", {})
    butterworth = filtering.get("butterworth", {})
    marker_augmentation = config.get("markerAugmentation", {})
    kinematics = config.get("kinematics", {})

    frame_start, frame_end = _frame_range(project.get("frame_range"))
    calibration_type = calibration.get("calibration_type", "calculate")
    if calibration_type == "convert":
        calibration_mode = "convert"
    else:
        calibration_mode = "board" if extrinsics.get("extrinsics_method") == "board" else "scene"

    participant_height = project.get("participant_height")
    participant_mass = project.get("participant_mass")
    return PipelineSettings(
        project_name=project_name,
        multi_person=bool(project.get("multi_person", False)),
        participant_height_m=_first_float(participant_height),
        participant_heights_m=_float_list(participant_height),
        participant_mass_kg=_first_float(participant_mass, 70.0) or 70.0,
        participant_masses_kg=_float_list(participant_mass),
        default_height_m=float(kinematics.get("default_height", 1.70)),
        frame_start=frame_start,
        frame_end=frame_end,
        pose_mode=str(pose.get("mode", "balanced")),
        pose_model=str(pose.get("pose_model", "Body_with_feet")),
        speed_preset=_speed_preset_from_pose(pose.get("mode")),
        calibration_mode=calibration_mode,
        intrinsics_inner_corners=tuple(intrinsics.get("intrinsics_corners_nb", [4, 7])),
        intrinsics_square_size_mm=float(intrinsics.get("intrinsics_square_size", 35.0)),
        intrinsics_extension=str(intrinsics.get("intrinsics_extension", "mp4")),
        extrinsics_inner_corners=tuple(extrinsics.get("board", {}).get("extrinsics_corners_nb", [4, 7])),
        extrinsics_square_size_mm=float(extrinsics.get("board", {}).get("extrinsics_square_size", 45.0)),
        extrinsics_extension=str(extrinsics.get("extrinsics_extension", "mp4")),
        extrinsics_board_position=str(extrinsics.get("board", {}).get("board_position", "horizontal")),
        external_calibration_format=str(convert.get("convert_from", "qualisys")),
        skip_synchronization=False,
        sync_times_seconds=_sync_times(synchronization.get("approx_time_maxspeed")),
        sync_search_range_seconds=float(synchronization.get("time_range_around_maxspeed", 2.0)),
        tracking_mode=str(pose.get("tracking_mode", "sports2d")),
        tracked_keypoint=str(
            config.get("personAssociation", {}).get("single_person", {}).get("tracked_keypoint", "Neck")
        ),
        manual_sync_selection=bool(synchronization.get("synchronization_gui", False)),
        marker_augmentation=bool(kinematics.get("use_augmentation", True)),
        use_simple_model=bool(kinematics.get("use_simple_model", False)),
        save_overlay_video=pose.get("save_video", "to_video") != "none",
        feet_on_floor=bool(marker_augmentation.get("feet_on_floor", False)),
        right_left_symmetry=bool(kinematics.get("right_left_symmetry", True)),
        filter_cutoff_hz=float(butterworth.get("cut_off_frequency", 6.0)),
        large_hip_knee_angles=float(kinematics.get("large_hip_knee_angles", 135.0)),
        trimmed_extrema_percent=float(kinematics.get("trimmed_extrema_percent", 0.5)),
    )


def _set_nested(target: dict[str, Any], source: dict[str, Any], path: tuple[str, ...]) -> None:
    target_cursor: dict[str, Any] = target
    source_cursor: dict[str, Any] = source
    for key in path[:-1]:
        target_cursor = target_cursor.setdefault(key, {})
        source_cursor = source_cursor.get(key, {})
    key = path[-1]
    if key in source_cursor:
        target_cursor[key] = source_cursor[key]


def _set_nested_if_missing(target: dict[str, Any], source: dict[str, Any], path: tuple[str, ...]) -> None:
    target_cursor: dict[str, Any] = target
    source_cursor: dict[str, Any] = source
    for key in path[:-1]:
        target_cursor = target_cursor.setdefault(key, {})
        source_cursor = source_cursor.get(key, {})
    key = path[-1]
    if key in source_cursor and key not in target_cursor:
        target_cursor[key] = source_cursor[key]


GUI_MANAGED_PATHS = [
    ("project", "project_dir"),
    ("project", "multi_person"),
    ("project", "participant_height"),
    ("project", "participant_mass"),
    ("project", "frame_range"),
    ("pose", "pose_model"),
    ("pose", "mode"),
    ("pose", "det_frequency"),
    ("pose", "save_video"),
    ("pose", "tracking_mode"),
    ("synchronization", "synchronization_gui"),
    ("synchronization", "approx_time_maxspeed"),
    ("synchronization", "time_range_around_maxspeed"),
    ("personAssociation", "single_person", "tracked_keypoint"),
    ("filtering", "butterworth", "cut_off_frequency"),
    ("markerAugmentation", "feet_on_floor"),
    ("kinematics", "use_augmentation"),
    ("kinematics", "use_simple_model"),
    ("kinematics", "right_left_symmetry"),
    ("kinematics", "default_height"),
    ("kinematics", "large_hip_knee_angles"),
    ("kinematics", "trimmed_extrema_percent"),
]

CALIBRATION_PATHS = [
    ("calibration", "calibration_type"),
    ("calibration", "calculate", "intrinsics", "intrinsics_extension"),
    ("calibration", "calculate", "intrinsics", "intrinsics_corners_nb"),
    ("calibration", "calculate", "intrinsics", "intrinsics_square_size"),
    ("calibration", "calculate", "extrinsics", "extrinsics_method"),
    ("calibration", "calculate", "extrinsics", "extrinsics_extension"),
    ("calibration", "calculate", "extrinsics", "board", "board_position"),
    ("calibration", "calculate", "extrinsics", "board", "extrinsics_corners_nb"),
    ("calibration", "calculate", "extrinsics", "board", "extrinsics_square_size"),
    ("calibration", "calculate", "extrinsics", "scene", "object_coords_3d"),
]

CONVERT_CALIBRATION_PATHS = [
    ("calibration", "calibration_type"),
    ("calibration", "convert", "convert_from"),
]

CONVERT_CALIBRATION_DEFAULT_PATHS = [
    ("calibration", "convert", "qualisys", "binning_factor"),
]


def merged_config(project_dir: Path, existing_config: dict[str, Any], settings: PipelineSettings) -> dict[str, Any]:
    generated = build_config_dict(project_dir, settings)
    merged = copy.deepcopy(existing_config)
    for path in GUI_MANAGED_PATHS:
        _set_nested(merged, generated, path)
    if settings.calibration_mode == "convert":
        for path in CONVERT_CALIBRATION_PATHS:
            _set_nested(merged, generated, path)
        for path in CONVERT_CALIBRATION_DEFAULT_PATHS:
            _set_nested_if_missing(merged, generated, path)
    else:
        for path in CALIBRATION_PATHS:
            _set_nested(merged, generated, path)
    return merged


def config_text(config: dict[str, Any]) -> str:
    return toml.dumps(config)
