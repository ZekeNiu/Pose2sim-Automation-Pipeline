from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import toml


VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".m4v", ".webm"}
CALIBRATION_SOURCE_EXTENSIONS = {".qca.txt", ".xcp", ".pickle", ".pkl", ".yml", ".yaml", ".xml"}


@dataclass
class ProjectStatus:
    project_dir: Path
    has_config: bool
    is_batch: bool
    trial_names: list[str] = field(default_factory=list)
    multi_person: bool = False
    has_videos: bool = False
    has_calibration_source: bool = False
    has_calibration_toml: bool = False
    has_pose: bool = False
    has_sync: bool = False
    has_pose_3d: bool = False
    has_kinematics: bool = False
    mot_files: list[Path] = field(default_factory=list)
    calibration_type: str | None = None

    @property
    def kind(self) -> str:
        labels: list[str] = []
        if self.is_batch:
            labels.append("批处理项目")
        if self.multi_person:
            labels.append("多人项目")
        if self.has_kinematics:
            labels.append("已分析项目")
        elif self.has_calibration_source and self.calibration_type == "convert":
            labels.append("已有外部校准项目")
        elif self.has_videos:
            labels.append("已有视频未分析项目")
        elif self.has_config:
            labels.append("新建但未分析项目")
        else:
            labels.append("空项目")
        return " / ".join(labels)

    @property
    def recommended_action(self) -> str:
        if self.has_kinematics:
            return "仅生成报告"
        if self.is_batch:
            return "按现有 Config 批量运行"
        if self.has_config and (self.has_videos or self.has_calibration_source or self.has_calibration_toml):
            return "按现有 Config 运行"
        return "保存配置并运行完整流程"

    @property
    def missing_steps(self) -> list[str]:
        steps: list[str] = []
        if not self.has_calibration_toml:
            steps.append("calibration")
        if not self.has_pose:
            steps.append("poseEstimation")
        if not self.has_sync:
            steps.append("synchronization")
        if not self.has_pose_3d:
            steps.extend(["personAssociation", "triangulation", "filtering"])
        if not self.has_kinematics:
            steps.extend(["markerAugmentation", "kinematics"])
        steps.append("reports")
        seen: set[str] = set()
        return [step for step in steps if not (step in seen or seen.add(step))]

    def summary_lines(self) -> list[str]:
        lines = [
            f"项目类型：{self.kind}",
            f"推荐操作：{self.recommended_action}",
            f"Config.toml：{'已存在' if self.has_config else '未发现'}",
            f"视频：{'已发现' if self.has_videos else '未发现'}",
            f"校准来源：{'外部校准文件' if self.has_calibration_source else ('已计算校准' if self.has_calibration_toml else '未发现')}",
            f"已分析结果：{'已发现 .mot' if self.has_kinematics else '未发现 .mot'}",
        ]
        if self.calibration_type:
            lines.append(f"配置中的 calibration_type：{self.calibration_type}")
        if self.trial_names:
            lines.append("试次目录：" + ", ".join(self.trial_names))
        if self.mot_files:
            lines.append("可报告 .mot：")
            lines.extend(f"- {path.relative_to(self.project_dir)}" for path in self.mot_files[:10])
            if len(self.mot_files) > 10:
                lines.append(f"- 另有 {len(self.mot_files) - 10} 个 .mot 文件")
        lines.append("说明：GUI 只按通用目录和 Config 内容识别状态，不按 Demo 名称做特殊处理。")
        return lines


def _safe_toml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return toml.load(path)
    except Exception:
        return {}


def _project_config(project_dir: Path) -> dict[str, Any]:
    return _safe_toml(project_dir / "Config.toml")


def _child_project_dirs(project_dir: Path) -> list[Path]:
    children: list[Path] = []
    if not project_dir.exists():
        return children
    for child in project_dir.iterdir():
        if not child.is_dir() or child.name.startswith("."):
            continue
        if child.name.lower() in {"source", "videos", "calibration", "pose", "pose-sync", "pose-3d", "kinematics"}:
            continue
        if (child / "Config.toml").exists() or (child / "videos").exists() or list(child.glob("*.mp4")):
            children.append(child)
    return sorted(children)


def _has_video(project_dir: Path) -> bool:
    for folder in [project_dir / "videos", project_dir]:
        if folder.exists() and any(path.suffix.lower() in VIDEO_EXTENSIONS for path in folder.iterdir() if path.is_file()):
            return True
    return False


def _has_calibration_source(project_dir: Path) -> bool:
    calibration_dir = project_dir / "calibration"
    if not calibration_dir.exists():
        return False
    for path in calibration_dir.rglob("*"):
        lower_name = path.name.lower()
        if any(lower_name.endswith(ext) for ext in CALIBRATION_SOURCE_EXTENSIONS):
            return True
    return False


def _has_calibration_toml(project_dir: Path) -> bool:
    calibration_dir = project_dir / "calibration"
    return calibration_dir.exists() and any(path.suffix.lower() == ".toml" for path in calibration_dir.rglob("*"))


def _mot_files(project_dir: Path) -> list[Path]:
    return sorted((project_dir / "kinematics").glob("*.mot"))


def inspect_project(project_dir: Path) -> ProjectStatus:
    project_dir = project_dir.resolve()
    config = _project_config(project_dir)
    children = _child_project_dirs(project_dir)
    is_batch = bool(children and (project_dir / "Config.toml").exists())
    configs = [config, *(_project_config(child) for child in children)]
    multi_person = any(bool(cfg.get("project", {}).get("multi_person")) for cfg in configs if cfg)
    calibration_type = config.get("calibration", {}).get("calibration_type") if config else None

    all_dirs = [project_dir, *children]
    mot_files = [mot for directory in all_dirs for mot in _mot_files(directory)]
    status = ProjectStatus(
        project_dir=project_dir,
        has_config=(project_dir / "Config.toml").exists(),
        is_batch=is_batch,
        trial_names=[child.name for child in children],
        multi_person=multi_person,
        has_videos=any(_has_video(directory) for directory in all_dirs),
        has_calibration_source=any(_has_calibration_source(directory) for directory in all_dirs),
        has_calibration_toml=any(_has_calibration_toml(directory) for directory in all_dirs),
        has_pose=any((directory / "pose").exists() and any((directory / "pose").iterdir()) for directory in all_dirs),
        has_sync=any((directory / "pose-sync").exists() and any((directory / "pose-sync").iterdir()) for directory in all_dirs),
        has_pose_3d=any((directory / "pose-3d").exists() and any((directory / "pose-3d").iterdir()) for directory in all_dirs),
        has_kinematics=bool(mot_files),
        mot_files=mot_files,
        calibration_type=str(calibration_type) if calibration_type is not None else None,
    )
    return status
