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
    scene_points_text: str = ""
    skip_synchronization: bool = False
    sync_times_seconds: list[float] = field(default_factory=list)
    sync_search_range_seconds: float = 2.0
    marker_augmentation: bool = True
    use_simple_model: bool = False
    save_overlay_video: bool = True
    feet_on_floor: bool = False
    right_left_symmetry: bool = True
    filter_cutoff_hz: float = 6.0
    large_hip_knee_angles: float = 135.0
    trimmed_extrema_percent: float = 0.5

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

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_chinese_lines(self) -> list[str]:
        lines = [
            f"Python: {self.python_path}",
            f"Pose2Sim: {self.pose2sim_version or '未检测到'}",
            f"OpenSim: {self.opensim_version or '未检测到'}",
            f"customtkinter: {self.customtkinter_version or '未检测到'}",
            f"plotly: {self.plotly_version or '未检测到'}",
            f"openpyxl: {self.openpyxl_version or '未检测到'}",
            f"ffmpeg: {self.ffmpeg_path or '未检测到'}",
            f"加速提示: {self.gpu_hint}",
        ]
        if self.errors:
            lines.append("问题:")
            lines.extend(f"- {err}" for err in self.errors)
        else:
            lines.append("环境检查通过。")
        return lines
