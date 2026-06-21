from __future__ import annotations

import argparse
import os
import sys
import traceback
from pathlib import Path

from .paths import WORKSPACE_ROOT, output_dir
from .report import generate_reports_for_project


STEP_LABELS = {
    "calibration": "相机校准",
    "poseEstimation": "2D 姿态识别",
    "synchronization": "多机位同步",
    "personAssociation": "人物匹配",
    "triangulation": "3D 三角化",
    "filtering": "3D 坐标滤波",
    "markerAugmentation": "标记点增强",
    "kinematics": "OpenSim 缩放与逆运动学",
    "reports": "报告生成",
}


DEFAULT_STEPS = [
    "calibration",
    "poseEstimation",
    "synchronization",
    "personAssociation",
    "triangulation",
    "filtering",
    "markerAugmentation",
    "kinematics",
    "reports",
]


def should_run_marker_augmentation(config_dicts: list[dict]) -> bool:
    return any(bool(config.get("kinematics", {}).get("use_augmentation", True)) for config in config_dicts)


def run_steps(project_dir: Path, steps: list[str], skip_synchronization: bool = False) -> None:
    from Pose2Sim.Pose2Sim import Pose2SimPipeline

    project_dir = project_dir.resolve()
    os.chdir(project_dir)
    if not (project_dir / "Config.toml").exists():
        raise FileNotFoundError(f"未找到配置文件: {project_dir / 'Config.toml'}")
    pipeline = Pose2SimPipeline(str(project_dir))
    marker_aug_failed = False
    stage_methods = {
        "calibration": pipeline.calibration,
        "poseEstimation": pipeline.poseEstimation,
        "synchronization": pipeline.synchronization,
        "personAssociation": pipeline.personAssociation,
        "triangulation": pipeline.triangulation,
        "filtering": pipeline.filtering,
        "kinematics": pipeline.kinematics,
    }

    for step in steps:
        if step == "synchronization" and skip_synchronization:
            print("跳过多机位同步：用户选择视频已硬同步。", flush=True)
            continue
        print(f"\n==== 开始：{STEP_LABELS.get(step, step)} ====", flush=True)
        if step == "reports":
            generate_reports_for_project(project_dir, output_dir(project_dir.name))
        elif step == "markerAugmentation":
            if not should_run_marker_augmentation(pipeline.config_dicts):
                print("跳过标记点增强：当前 Config 已关闭 use_augmentation。", flush=True)
                continue
            try:
                pipeline.markerAugmentation()
            except Exception as exc:
                marker_aug_failed = True
                for config in pipeline.config_dicts:
                    config.setdefault("kinematics", {})["use_augmentation"] = False
                print(f"标记点增强失败，已切换为不使用增强继续运行: {exc}", flush=True)
        elif step == "kinematics":
            if marker_aug_failed:
                for config in pipeline.config_dicts:
                    config.setdefault("kinematics", {})["use_augmentation"] = False
            stage_methods["kinematics"]()
        else:
            if step not in stage_methods:
                raise ValueError(f"未知运行阶段: {step}")
            stage_methods[step]()
        print(f"==== 完成：{STEP_LABELS.get(step, step)} ====", flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Pose2Sim Chinese GUI pipeline commands.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--project-dir", required=True)
    run_parser.add_argument("--steps", nargs="*", default=DEFAULT_STEPS)
    run_parser.add_argument("--skip-synchronization", action="store_true")

    report_parser = subparsers.add_parser("reports")
    report_parser.add_argument("--project-dir", required=True)

    args = parser.parse_args(argv)
    try:
        project_dir = Path(args.project_dir)
        project_dir.resolve().relative_to(WORKSPACE_ROOT.resolve())
        if args.command == "run":
            run_steps(project_dir, args.steps, skip_synchronization=args.skip_synchronization)
        elif args.command == "reports":
            generate_reports_for_project(project_dir, output_dir(project_dir.name))
        return 0
    except Exception:
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
