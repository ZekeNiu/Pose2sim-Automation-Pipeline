from __future__ import annotations

from pose2sim_pipeline_gui.app import CALISCOPE_USAGE_HELP_TEXT, CALISCOPE_USAGE_HELP_TITLE


def test_caliscope_usage_help_is_user_facing() -> None:
    assert CALISCOPE_USAGE_HELP_TITLE == "Caliscope 使用说明"
    for phrase in [
        "什么时候用 Caliscope",
        "打开 Caliscope 校准",
        "我已完成，导入校准结果",
        "相机不能移动",
        "相机数量必须和本项目测试视频数量一致",
        "机位顺序",
    ]:
        assert phrase in CALISCOPE_USAGE_HELP_TEXT

    lowered = CALISCOPE_USAGE_HELP_TEXT.lower()
    assert "camera_array" not in lowered
    assert "aniposelib" not in lowered
    assert "toml" not in lowered
