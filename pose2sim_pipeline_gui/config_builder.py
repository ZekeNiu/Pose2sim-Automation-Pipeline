from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

import toml

from .environment import pose2sim_uses_percent_trimmed_extrema
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

EXTERNAL_CALIBRATION_FORMAT_OPTIONS = {
    "Qualisys（.qca.txt，常见实验室系统）": "qualisys",
    "Vicon（.xcp）": "vicon",
    "OpenCap（.pickle / .pkl）": "opencap",
    "EasyMocap（.yml / .yaml）": "easymocap",
    "BioCV（.calib）": "biocv",
    "OptiTrack（高级，需符合 Pose2Sim 官方要求）": "optitrack",
    "Caliscope（高级，通常无需转换）": "caliscope",
    "Anipose（高级，通常无需转换）": "anipose",
    "FreeMoCap（高级，通常无需转换）": "freemocap",
}

EXTERNAL_CALIBRATION_FORMAT_LABELS = {value: label for label, value in EXTERNAL_CALIBRATION_FORMAT_OPTIONS.items()}

EXTERNAL_CALIBRATION_EXTENSIONS = {
    "qualisys": [".qca.txt"],
    "vicon": [".xcp"],
    "opencap": [".pickle", ".pkl"],
    "easymocap": [".yml", ".yaml"],
    "biocv": [".calib"],
}

EXTERNAL_CALIBRATION_DESCRIPTIONS = {
    "qualisys": "导入 Qualisys 导出的 .qca.txt 文件。Pose2Sim 会转换为 calibration/Calib_qualisys.toml。",
    "vicon": "导入 Vicon 的 .xcp 文件。请确认相机数量和测试视频机位一致。",
    "opencap": "导入 OpenCap 的 .pickle/.pkl 校准文件，通常需要成组文件。",
    "easymocap": "导入 EasyMocap 的 intri/extri .yml 或 .yaml 文件。",
    "biocv": "导入 BioCV 的 .calib 文件。",
    "optitrack": "高级格式。GUI 只复制文件并写入 Config，请确认文件结构符合 Pose2Sim 官方说明。",
    "caliscope": "高级格式。Pose2Sim 通常可直接使用，GUI 只复制文件并写入 Config。",
    "anipose": "高级格式。Pose2Sim 通常可直接使用，GUI 只复制文件并写入 Config。",
    "freemocap": "高级格式。Pose2Sim 通常可直接使用，GUI 只复制文件并写入 Config。",
}


def parse_scene_points(text: str) -> list[list[float]]:
    if not text.strip():
        return DEFAULT_SCENE_POINTS
    stripped = text.strip()
    if stripped.startswith("["):
        try:
            parsed = ast.literal_eval(stripped)
        except Exception as exc:
            raise ValueError("场景点坐标格式应为 [[X,Y,Z], ...]，或表格行 P1, X, Y, Z, 说明。") from exc
        if not isinstance(parsed, list):
            raise ValueError("场景点坐标应为列表。")
        raw_points = parsed
    else:
        raw_points = []
        for line in stripped.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [part.strip() for part in re.split(r"[\t,，]+", line) if part.strip()]
            if not parts or parts[0].lower() in {"点编号", "编号", "point", "id"}:
                continue
            try:
                float(parts[0])
                point = parts[:3]
            except ValueError:
                point = parts[1:4]
            raw_points.append(point)

    if len(raw_points) < 6:
        raise ValueError("外参场景点至少需要 6 个点，建议 10 个以上。")
    points: list[list[float]] = []
    for point in raw_points:
        if not isinstance(point, (list, tuple)) or len(point) < 3:
            raise ValueError("每个场景点必须包含 X、Y、Z 三个真实世界坐标。")
        points.append([float(point[0]), float(point[1]), float(point[2])])
    return points


def _pose_speed_values(settings: PipelineSettings) -> tuple[str, int]:
    if settings.speed_preset == "fast":
        return "lightweight", 8
    if settings.speed_preset == "accurate":
        return "performance", 2
    return settings.pose_mode, 4


def trimmed_extrema_config_value(value: float) -> float:
    numeric = float(value)
    if pose2sim_uses_percent_trimmed_extrema():
        return numeric * 100 if 0 < numeric <= 1 else numeric
    return numeric / 100 if numeric > 1 else numeric


def build_config_dict(project_dir: Path, settings: PipelineSettings) -> dict[str, Any]:
    mode, det_frequency = _pose_speed_values(settings)
    sync_value: str | list[float] = "auto"
    if settings.sync_times_seconds:
        sync_value = [float(v) for v in settings.sync_times_seconds]

    extrinsics_method = "board" if settings.calibration_mode == "board" else "scene"
    scene_points = parse_scene_points(settings.scene_points_text) if extrinsics_method == "scene" else DEFAULT_SCENE_POINTS
    config: dict[str, Any] = {
        "project": {
            "project_dir": str(project_dir.resolve()),
            "multi_person": bool(settings.multi_person),
            "participant_height": settings.participant_height_value(),
            "participant_mass": settings.participant_mass_value(),
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
            "save_video": "to_video" if settings.save_overlay_video else "none",
            "output_format": "openpose",
            "average_likelihood_threshold_pose": 0.5,
            "tracking_mode": settings.tracking_mode,
            "max_distance_px": 100,
            "handle_LR_swap": False,
            "undistort_points": False,
        },
        "synchronization": {
            "synchronization_gui": bool(settings.manual_sync_selection),
            "display_sync_plots": False,
            "save_sync_plots": True,
            "keypoints_to_consider": "all",
            "approx_time_maxspeed": sync_value,
            "time_range_around_maxspeed": float(settings.sync_search_range_seconds),
            "likelihood_threshold_synchronization": 0.4,
            "filter_cutoff": 6,
            "filter_order": 4,
        },
        "calibration": {
            "calibration_type": "convert" if settings.calibration_mode == "convert" else "calculate",
            "calculate": {
                "save_debug_images": True,
                "intrinsics": {
                    "overwrite_intrinsics": False,
                    "intrinsics_extension": settings.intrinsics_extension,
                    "extract_every_N_sec": 1,
                    "intrinsics_corners_nb": list(settings.intrinsics_inner_corners),
                    "intrinsics_square_size": float(settings.intrinsics_square_size_mm),
                    "show_detection_intrinsics": True,
                },
                "extrinsics": {
                    "calculate_extrinsics": True,
                    "extrinsics_method": extrinsics_method,
                    "extrinsics_extension": settings.extrinsics_extension,
                    "show_reprojection_error": True,
                    "moving_cameras": False,
                    "board": {
                        "board_position": settings.extrinsics_board_position,
                        "extrinsics_corners_nb": list(settings.extrinsics_inner_corners),
                        "extrinsics_square_size": float(settings.extrinsics_square_size_mm),
                    },
                    "scene": {
                        "object_coords_3d": scene_points,
                    },
                },
            },
            "convert": {
                "convert_from": settings.external_calibration_format,
                "caliscope": {},
                "qualisys": {"binning_factor": 1},
                "optitrack": {},
                "vicon": {},
                "opencap": {},
                "easymocap": {},
                "biocv": {},
                "anipose": {},
                "freemocap": {},
            },
        },
        "personAssociation": {
            "likelihood_threshold_association": 0.3,
            "single_person": {
                "likelihood_threshold_association": 0.3,
                "reproj_error_threshold_association": 20,
                "tracked_keypoint": settings.tracked_keypoint,
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
            "feet_on_floor": bool(settings.feet_on_floor),
            "make_c3d": True,
        },
        "kinematics": {
            "use_augmentation": bool(settings.marker_augmentation),
            "use_simple_model": bool(settings.use_simple_model),
            "filter_ik": False,
            "ik_filter_type": "acc_minimizing",
            "parallel_workers_kinematics": "auto",
            "right_left_symmetry": bool(settings.right_left_symmetry),
            "default_height": float(settings.default_height_m),
            "remove_individual_scaling_setup": True,
            "remove_individual_ik_setup": True,
            "large_hip_knee_angles": float(settings.large_hip_knee_angles),
            "trimmed_extrema_percent": trimmed_extrema_config_value(settings.trimmed_extrema_percent),
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
