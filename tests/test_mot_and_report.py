from __future__ import annotations

import shutil
from pathlib import Path

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
        (project_dir / "kinematics" / "sample.mot").write_text(SAMPLE_MOT, encoding="utf-8")

        html_path, excel_path = generate_reports(project_dir, output_dir)

        assert html_path.exists()
        assert excel_path.exists()
        html = html_path.read_text(encoding="utf-8")
        assert "左膝屈伸" in html
        assert "质量诊断与解释边界" in html
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
