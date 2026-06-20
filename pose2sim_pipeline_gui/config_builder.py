from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import toml

from .models import PipelineSettings


DEFAULT_SCENE_POINTS = [
    [-2.0, 0.3, 0.0],
    [-2.0, 0.0, 0.0],
    [-2.0, 0.0, 0.05],
    [-2.0, -0.3, 0.0],
    [0.0, 0.3, 0.0],
    [0.0, 0.0, 0.0],
    [0.0, 0.0, 0.05],
    [0.0, -0.3, 0.0],
    [1.0, 0.3, 0.0],
    [1.0, -0.3, 0.0],
]


def parse_scene_points(text: str) -> list[list[float]]:
    if not text.strip():
        return DEFAULT_SCENE_POINTS
    try:
        parsed = ast.literal_eval(text.strip())
    except Exception as exc:
        raise ValueError("场景点坐标格式应为 [[X,Y,Z], ...]。") from exc
    if not isinstance(parsed, list) or len(parsed) < 6:
        raise ValueError("外参场景点至少需要 6 个点，建议 10 个以上。")
    points: list[list[float]] = []
    for point in parsed:
        if not isinstance(point, (list, tuple)) or len(point) != 3:
            raise ValueError("每个场景点必须是 [X, Y, Z] 三个数。")
        points.append([float(point[0]), float(point[1]), float(point[2])])
    return points


def _pose_speed_values(settings: PipelineSettings) -> tuple[str, int]:
    if settings.speed_preset == "fast":
        return "lightweight", 8
    if settings.speed_preset == "accurate":
        return "performance", 2
    return settings.pose_mode, 4


def build_config_dict(project_dir: Path, settings: PipelineSettings) -> dict[str, Any]:
    mode, det_frequency = _pose_speed_values(settings)
    sync_value: str | list[float] = "auto"
    if settings.sync_times_seconds:
        sync_value = [float(v) for v in settings.sync_times_seconds]

    extrinsics_method = "scene" if settings.calibration_mode == "scene" else "board"
    config: dict[str, Any] = {
        "project": {
            "project_dir": str(project_dir.resolve()),
            "multi_person": False,
            "participant_height": settings.participant_height_value(),
            "participant_mass": float(settings.participant_mass_kg),
            "frame_rate": "auto",
            "frame_range": settings.frame_range_value(),
            "exclude_from_batch": [],
        },
        "pose": {
            "pose_model": settings.pose_model,
            "mode": mode,
            "det_frequency": int(det_frequency),
            "device": "auto",
            "backend": "auto",
            "parallel_workers_pose": "auto",
            "display_detection": False,
            "overwrite_pose": False,
            "save_video": "to_video",
            "output_format": "openpose",
            "average_likelihood_threshold_pose": 0.5,
            "tracking_mode": "sports2d",
            "max_distance_px": 100,
            "handle_LR_swap": False,
            "undistort_points": False,
        },
        "synchronization": {
            "synchronization_gui": False,
            "display_sync_plots": False,
            "save_sync_plots": True,
            "keypoints_to_consider": "all",
            "approx_time_maxspeed": sync_value,
            "time_range_around_maxspeed": 2.0,
            "likelihood_threshold_synchronization": 0.4,
            "filter_cutoff": 6,
            "filter_order": 4,
        },
        "calibration": {
            "calibration_type": "calculate",
            "calculate": {
                "save_debug_images": True,
                "intrinsics": {
                    "overwrite_intrinsics": False,
                    "intrinsics_extension": "mp4",
                    "extract_every_N_sec": 1,
                    "intrinsics_corners_nb": list(settings.intrinsics_inner_corners),
                    "intrinsics_square_size": float(settings.intrinsics_square_size_mm),
                    "show_detection_intrinsics": True,
                },
                "extrinsics": {
                    "calculate_extrinsics": True,
                    "extrinsics_method": extrinsics_method,
                    "extrinsics_extension": "mp4",
                    "show_reprojection_error": True,
                    "moving_cameras": False,
                    "board": {
                        "board_position": settings.extrinsics_board_position,
                        "extrinsics_corners_nb": list(settings.extrinsics_inner_corners),
                        "extrinsics_square_size": float(settings.extrinsics_square_size_mm),
                    },
                    "scene": {
                        "object_coords_3d": parse_scene_points(settings.scene_points_text),
                    },
                },
            },
            "convert": {
                "convert_from": "qualisys",
                "qualisys": {"binning_factor": 1},
            },
        },
        "personAssociation": {
            "likelihood_threshold_association": 0.3,
            "single_person": {
                "likelihood_threshold_association": 0.3,
                "reproj_error_threshold_association": 20,
                "tracked_keypoint": "Neck",
            },
            "multi_person": {
                "reconstruction_error_threshold": 0.1,
                "min_affinity": 0.2,
            },
        },
        "triangulation": {
            "reproj_error_threshold_triangulation": 15,
            "likelihood_threshold_triangulation": 0.3,
            "min_cameras_for_triangulation": 2,
            "max_distance_m": 1.0,
            "max_unseen_frames": 100,
            "interp_if_gap_smaller_than": 20,
            "interpolation": "linear",
            "remove_incomplete_frames": False,
            "sections_to_keep": "all",
            "min_chunk_size": 10,
            "fill_large_gaps_with": "last_value",
            "show_interp_indices": True,
            "make_c3d": True,
        },
        "filtering": {
            "reject_outliers": True,
            "filter": True,
            "filter_ik": False,
            "type": "butterworth",
            "display_figures": False,
            "save_filt_plots": True,
            "make_c3d": True,
            "butterworth": {
                "cut_off_frequency": float(settings.filter_cutoff_hz),
                "order": 4,
            },
        },
        "markerAugmentation": {
            "feet_on_floor": False,
            "make_c3d": True,
        },
        "kinematics": {
            "use_augmentation": bool(settings.marker_augmentation),
            "use_simple_model": bool(settings.use_simple_model),
            "parallel_workers_kinematics": "auto",
            "right_left_symmetry": True,
            "default_height": float(settings.default_height_m),
            "remove_individual_scaling_setup": True,
            "remove_individual_ik_setup": True,
            "large_hip_knee_angles": float(settings.large_hip_knee_angles),
            "trimmed_extrema_percent": float(settings.trimmed_extrema_percent),
        },
        "logging": {
            "use_custom_logging": False,
        },
    }
    return config


def write_config(project_dir: Path, settings: PipelineSettings) -> Path:
    config_path = project_dir / "Config.toml"
    config = build_config_dict(project_dir, settings)
    with config_path.open("w", encoding="utf-8") as handle:
        toml.dump(config, handle)
    return config_path

