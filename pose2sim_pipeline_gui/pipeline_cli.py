from __future__ import annotations

import argparse
import os
import sys
import traceback
from pathlib import Path

import toml

from .paths import WORKSPACE_ROOT, output_dir
from .report import generate_reports


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


def _load_config(project_dir: Path) -> dict:
    config_path = project_dir / "Config.toml"
    if not config_path.exists():
        raise FileNotFoundError(f"未找到配置文件: {config_path}")
    config = toml.load(config_path)
    config.setdefault("project", {})
    config["project"]["project_dir"] = str(project_dir.resolve())
    return config


def run_steps(project_dir: Path, steps: list[str], skip_synchronization: bool = False) -> None:
    from Pose2Sim import Pose2Sim

    project_dir = project_dir.resolve()
    os.chdir(project_dir)
    config = _load_config(project_dir)
    marker_aug_failed = False

    for step in steps:
        if step == "synchronization" and skip_synchronization:
            print("跳过多机位同步：用户选择视频已硬同步。", flush=True)
            continue
        print(f"\n==== 开始：{STEP_LABELS.get(step, step)} ====", flush=True)
        if step == "reports":
            generate_reports(project_dir, output_dir(project_dir.name))
        elif step == "markerAugmentation":
            try:
                Pose2Sim.markerAugmentation(config)
            except Exception as exc:
                marker_aug_failed = True
                config.setdefault("kinematics", {})["use_augmentation"] = False
                print(f"标记点增强失败，已切换为不使用增强继续运行: {exc}", flush=True)
        elif step == "kinematics":
            if marker_aug_failed:
                config.setdefault("kinematics", {})["use_augmentation"] = False
            Pose2Sim.kinematics(config)
        else:
            getattr(Pose2Sim, step)(config)
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
            generate_reports(project_dir, output_dir(project_dir.name))
        return 0
    except Exception:
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

