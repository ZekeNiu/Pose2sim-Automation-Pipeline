from __future__ import annotations

import shutil
from pathlib import Path

import pose2sim_pipeline_gui.report as report_module
from pose2sim_pipeline_gui.mot import angle_columns, read_mot
from pose2sim_pipeline_gui.paths import OUTPUTS_DIR, PROJECTS_DIR
from pose2sim_pipeline_gui.report import generate_reports, generate_reports_for_project


SAMPLE_MOT = """Coordinates
version=1
nRows=2
nColumns=6
inDegrees=yes
endheader
time\tpelvis_tx\tpelvis_tilt\thip_flexion_l\tknee_angle_l\tankle_angle_l
0.0\t0.0\t1.0\t20.0\t30.0\t5.0
0.1\t0.0\t2.0\t25.0\t40.0\t6.0
"""

SAMPLE_MOT_WITH_UNKNOWN = """Coordinates
version=1
nRows=2
nColumns=7
inDegrees=yes
endheader
time\tpelvis_tx\tpelvis_tilt\thip_flexion_l\tknee_angle_l\tankle_angle_l\tunknown_debug_coord
0.0\t0.0\t1.0\t20.0\t30.0\t5.0\t99.0
0.1\t0.0\t2.0\t25.0\t40.0\t6.0\t98.0
"""

SAMPLE_LOGS = """
Intrinsics error: 0.308 px for each cameras.
--> Residual (RMS) calibration errors for each camera are respectively [15.272, 20.679] px,
which corresponds to [34.955, 44.725] mm.
--> Camera cam02 and cam01: -31 frames offset (-31 on the selected section), correlation 0.93.
--> Mean reprojection error for Neck point on all frames is 34.4 px, which roughly corresponds to 78.7 mm.
--> Mean reprojection error for all points on frames 31 to 338 is 7.2 px, which roughly corresponds to 16.5 mm.
In average, 0.0 cameras had to be excluded.
"""

SAMPLE_MARKER_ERRORS = """OpenSim marker errors
endheader
time marker_error_RMS marker_error_max
0.0 0.1534 0.7569
0.1 0.1400 0.6000
"""


def test_read_mot_excludes_translation_columns(tmp_path: Path) -> None:
    mot_path = tmp_path / "sample.mot"
    mot_path.write_text(SAMPLE_MOT, encoding="utf-8")
    mot = read_mot(mot_path)
    assert mot.in_degrees is True
    assert angle_columns(mot.frame) == ["pelvis_tilt", "hip_flexion_l", "knee_angle_l", "ankle_angle_l"]


def test_generate_reports_from_mot() -> None:
    project_dir = PROJECTS_DIR / "_test_report"
    output_dir = OUTPUTS_DIR / "_test_report"
    shutil.rmtree(project_dir, ignore_errors=True)
    shutil.rmtree(output_dir, ignore_errors=True)
    try:
        (project_dir / "kinematics").mkdir(parents=True)
        (project_dir / "kinematics" / "sample.mot").write_text(SAMPLE_MOT_WITH_UNKNOWN, encoding="utf-8")
        (project_dir / "kinematics" / "_ik_marker_errors.sto").write_text(SAMPLE_MARKER_ERRORS, encoding="utf-8")
        (project_dir / "logs.txt").write_text(SAMPLE_LOGS, encoding="utf-8")
        (project_dir / "pose").mkdir()
        (project_dir / "pose" / "cam01_pose.mp4").write_bytes(b"overlay")
        (project_dir / "videos").mkdir()
        (project_dir / "videos" / "cam01.mp4").write_bytes(b"raw")

        html_path, excel_path = generate_reports(project_dir, output_dir)

        assert html_path.exists()
        assert excel_path.exists()
        html = html_path.read_text(encoding="utf-8")
        assert "左膝屈伸" in html
        assert "质量诊断与解释边界" in html
        assert "合理区间" in html
        assert "16.5 mm" in html
        assert "16.500 m" not in html
        assert "角度来源：OpenSim 逆运动学 .mot 文件；单位：度。" not in html
        assert "<title>Pose2sim运动学分析报告</title>" in html
        assert "<h1>Pose2sim运动学分析报告</h1>" in html
        assert "OpenSim 查看说明" not in html
        assert "叠加检测视频，已转为浏览器兼容视频" not in html
        assert "当前报告包含 1 个可解析 .mot 文件。" not in html
        assert "<select id='subject-select'>" not in html
        assert "cam01_pose.mp4" in html
        assert "cam01.mp4" not in html
        assert "已隐藏 1 个辅助坐标或未知指标" in html
        assert "unknown debug coord" not in html
    finally:
        shutil.rmtree(project_dir, ignore_errors=True)
        shutil.rmtree(output_dir, ignore_errors=True)


def test_generate_reports_from_multiple_mot_files() -> None:
    project_dir = PROJECTS_DIR / "_test_report_multi"
    output_dir = OUTPUTS_DIR / "_test_report_multi"
    shutil.rmtree(project_dir, ignore_errors=True)
    shutil.rmtree(output_dir, ignore_errors=True)
    try:
        (project_dir / "kinematics").mkdir(parents=True)
        (project_dir / "kinematics" / "trial_P1.mot").write_text(SAMPLE_MOT, encoding="utf-8")
        (project_dir / "kinematics" / "trial_P2.mot").write_text(SAMPLE_MOT, encoding="utf-8")

        html_path, excel_path = generate_reports(project_dir, output_dir)

        assert html_path.exists()
        assert excel_path.exists()
        html = html_path.read_text(encoding="utf-8")
        assert "subject-select" in html
        assert "P1" in html
        assert "P2" in html
    finally:
        shutil.rmtree(project_dir, ignore_errors=True)
        shutil.rmtree(output_dir, ignore_errors=True)


def test_report_video_transcodes_non_browser_compatible_overlay(monkeypatch) -> None:
    project_dir = PROJECTS_DIR / "_test_report_video_transcode"
    output_dir = OUTPUTS_DIR / "_test_report_video_transcode"
    shutil.rmtree(project_dir, ignore_errors=True)
    shutil.rmtree(output_dir, ignore_errors=True)

    def fake_probe(_path: Path) -> bool:
        return False

    def fake_transcode(_source: Path, target: Path) -> bool:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"transcoded")
        return True

    monkeypatch.setattr(report_module, "_is_browser_compatible_video", fake_probe)
    monkeypatch.setattr(report_module, "_transcode_video_for_browser", fake_transcode)
    try:
        (project_dir / "kinematics").mkdir(parents=True)
        (project_dir / "kinematics" / "sample.mot").write_text(SAMPLE_MOT, encoding="utf-8")
        (project_dir / "pose").mkdir()
        (project_dir / "pose" / "cam01_pose.mp4").write_bytes(b"overlay")

        html_path, _excel_path = generate_reports(project_dir, output_dir)

        assert (output_dir / "reports" / "media" / "cam01_pose.mp4").read_bytes() == b"transcoded"
        assert "叠加检测视频，已转为浏览器兼容视频" not in html_path.read_text(encoding="utf-8")
    finally:
        shutil.rmtree(project_dir, ignore_errors=True)
        shutil.rmtree(output_dir, ignore_errors=True)


def test_generate_batch_report_index() -> None:
    project_dir = PROJECTS_DIR / "_test_report_batch"
    output_dir = OUTPUTS_DIR / "_test_report_batch"
    shutil.rmtree(project_dir, ignore_errors=True)
    shutil.rmtree(output_dir, ignore_errors=True)
    try:
        trial = project_dir / "Trial_1"
        (trial / "kinematics").mkdir(parents=True)
        (trial / "kinematics" / "sample.mot").write_text(SAMPLE_MOT, encoding="utf-8")

        index_path, _excel_path = generate_reports_for_project(project_dir, output_dir)

        assert index_path.exists()
        html = index_path.read_text(encoding="utf-8")
        assert "Trial_1" in html
        assert "HTML 报告" in html
    finally:
        shutil.rmtree(project_dir, ignore_errors=True)
        shutil.rmtree(output_dir, ignore_errors=True)


def test_generate_reports_for_project_exports_pose2sim_outputs() -> None:
    project_dir = PROJECTS_DIR / "_test_report_export"
    output_dir = OUTPUTS_DIR / "_test_report_export"
    shutil.rmtree(project_dir, ignore_errors=True)
    shutil.rmtree(output_dir, ignore_errors=True)
    try:
        (project_dir / "kinematics").mkdir(parents=True)
        (project_dir / "kinematics" / "sample.mot").write_text(SAMPLE_MOT, encoding="utf-8")
        (project_dir / "kinematics" / "sample.osim").write_text("osim", encoding="utf-8")
        (project_dir / "source" / "videos").mkdir(parents=True)
        (project_dir / "source" / "videos" / "cam01.mp4").write_bytes(b"source")

        generate_reports_for_project(project_dir, output_dir)

        assert (output_dir / "kinematics" / "sample.mot").exists()
        assert (output_dir / "kinematics" / "sample.osim").exists()
        assert (output_dir / "kinematics" / "OpenSim_查看说明.txt").exists()
        assert not (output_dir / "source").exists()
    finally:
        shutil.rmtree(project_dir, ignore_errors=True)
        shutil.rmtree(output_dir, ignore_errors=True)
