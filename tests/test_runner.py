from __future__ import annotations

from pose2sim_pipeline_gui.runner import summarize_error


def test_summarize_error_returns_last_relevant_error_line() -> None:
    lines = [
        "开始运行",
        "ValueError: 缺少 Config.toml",
        "清理临时文件",
    ]

    assert summarize_error(lines, 1) == "ValueError: 缺少 Config.toml"


def test_summarize_error_handles_chinese_failure_lines() -> None:
    lines = [
        "开始运行",
        "外部校准导入失败: 文件类型不匹配",
    ]

    assert summarize_error(lines, 1) == "外部校准导入失败: 文件类型不匹配"


def test_summarize_error_returns_none_on_success() -> None:
    assert summarize_error(["Traceback from previous run"], 0) is None

