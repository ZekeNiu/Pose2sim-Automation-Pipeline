from __future__ import annotations

from pathlib import Path

from pose2sim_pipeline_gui.project_state import inspect_project


def test_inspect_empty_project(tmp_path: Path) -> None:
    status = inspect_project(tmp_path)

    assert status.kind == "空项目"
    assert status.recommended_action == "保存配置并运行完整流程"


def test_inspect_external_calibration_without_demo_name(tmp_path: Path) -> None:
    (tmp_path / "Config.toml").write_text(
        "[calibration]\ncalibration_type='convert'\n[project]\nmulti_person=false\n",
        encoding="utf-8",
    )
    (tmp_path / "calibration").mkdir()
    (tmp_path / "calibration" / "capture.qca.txt").write_text("qca", encoding="utf-8")
    (tmp_path / "videos").mkdir()
    (tmp_path / "videos" / "cam01.mp4").write_bytes(b"fake")

    status = inspect_project(tmp_path)

    assert status.has_calibration_source is True
    assert status.calibration_type == "convert"
    assert "已有外部校准项目" in status.kind
    assert status.recommended_action == "按现有 Config 运行"
    assert status.missing_steps[0] == "calibration"


def test_inspect_batch_and_multiperson_project(tmp_path: Path) -> None:
    (tmp_path / "Config.toml").write_text("[project]\nmulti_person=true\n", encoding="utf-8")
    trial = tmp_path / "Trial_1"
    (trial / "kinematics").mkdir(parents=True)
    (trial / "Config.toml").write_text("[project]\nframe_range='auto'\n", encoding="utf-8")
    (trial / "kinematics" / "trial_P1.mot").write_text("fake", encoding="utf-8")

    status = inspect_project(tmp_path)

    assert status.is_batch is True
    assert status.multi_person is True
    assert status.has_kinematics is True
    assert "批处理项目" in status.kind
    assert "多人项目" in status.kind
    assert status.recommended_action == "仅生成报告"
