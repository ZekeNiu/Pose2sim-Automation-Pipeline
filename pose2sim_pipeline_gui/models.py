from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class PipelineSettings:
    project_name: str
    multi_person: bool = False
    participant_height_m: float | None = None
    participant_heights_m: list[float] = field(default_factory=list)
    participant_mass_kg: float = 70.0
    participant_masses_kg: list[float] = field(default_factory=list)
    default_height_m: float = 1.70
    frame_start: int | None = None
    frame_end: int | None = None
    pose_mode: str = "balanced"
    pose_model: str = "Body_with_feet"
    speed_preset: str = "balanced"
    calibration_mode: str = "scene"
    intrinsics_inner_corners: tuple[int, int] = (4, 7)
    intrinsics_square_size_mm: float = 35.0
    intrinsics_extension: str = "mp4"
    extrinsics_inner_corners: tuple[int, int] = (4, 7)
    extrinsics_square_size_mm: float = 45.0
    extrinsics_extension: str = "mp4"
    extrinsics_board_position: str = "horizontal"
    external_calibration_format: str = "qualisys"
    scene_points_text: str = ""
    skip_synchronization: bool = False
    sync_times_seconds: list[float] = field(default_factory=list)
    sync_search_range_seconds: float = 2.0
    tracking_mode: str = "sports2d"
    tracked_keypoint: str = "Neck"
    manual_sync_selection: bool = False
    marker_augmentation: bool = True
    use_simple_model: bool = False
    save_overlay_video: bool = True
    feet_on_floor: bool = False
    right_left_symmetry: bool = True
    filter_cutoff_hz: float = 6.0
    large_hip_knee_angles: float = 90.0
    trimmed_extrema_percent: float = 50.0

    def frame_range_value(self) -> str | list[int]:
        if self.frame_start is None or self.frame_end is None:
            return "auto"
        if self.frame_end <= self.frame_start:
            raise ValueError("结束帧必须大于开始帧。")
        return [int(self.frame_start), int(self.frame_end)]

    def participant_height_value(self) -> str | float | list[float]:
        if self.multi_person and self.participant_heights_m:
            return [float(v) for v in self.participant_heights_m]
        return "auto" if self.participant_height_m is None else float(self.participant_height_m)

    def participant_mass_value(self) -> float | list[float]:
        if self.multi_person and self.participant_masses_kg:
            return [float(v) for v in self.participant_masses_kg]
        return float(self.participant_mass_kg)


@dataclass
class EnvironmentStatus:
    python_path: Path
    pose2sim_version: str | None
    opensim_version: str | None
    customtkinter_version: str | None
    plotly_version: str | None
    openpyxl_version: str | None
    ffmpeg_path: str | None
    gpu_hint: str
    errors: list[str] = field(default_factory=list)
    pandas_version: str | None = None
    pillow_version: str | None = None
    toml_version: str | None = None
    ffprobe_path: str | None = None
    warnings: list[str] = field(default_factory=list)
    python_version: str | None = None
    python_version_info: tuple[int, int, int] | None = None
    caliscope_version: str | None = None
    pyside6_version: str | None = None
    caliscope_gui_available: bool = False

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_chinese_lines(self) -> list[str]:
        python_label = f"{self.python_path}"
        if self.python_version:
            python_label = f"{python_label} ({self.python_version})"
        lines = [
            f"Python: {python_label}",
            f"Pose2Sim: {self.pose2sim_version or '未检测到'}",
            f"OpenSim: {self.opensim_version or '未检测到'}",
            f"customtkinter: {self.customtkinter_version or '未检测到'}",
            f"plotly: {self.plotly_version or '未检测到'}",
            f"openpyxl: {self.openpyxl_version or '未检测到'}",
            f"pandas: {self.pandas_version or '未检测到'}",
            f"Pillow: {self.pillow_version or '未检测到'}",
            f"toml: {self.toml_version or '未检测到'}",
            f"Caliscope: {self.caliscope_version or '未检测到'}",
            f"PySide6: {self.pyside6_version or '未检测到'}",
            f"Caliscope GUI: {'可用' if self.caliscope_gui_available else '未检测到'}",
            f"ffmpeg: {self.ffmpeg_path or '未检测到'}",
            f"ffprobe: {self.ffprobe_path or '未检测到'}",
            f"加速提示: {self.gpu_hint}",
        ]
        if self.warnings:
            lines.append("提醒:")
            lines.extend(f"- {warning}" for warning in self.warnings)
        if self.errors:
            lines.append("问题:")
            lines.extend(f"- {err}" for err in self.errors)
        else:
            lines.append("环境检查通过。")
        return lines
