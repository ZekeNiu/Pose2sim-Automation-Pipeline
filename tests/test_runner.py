from __future__ import annotations

from pathlib import Path

from pose2sim_pipeline_gui.runner import PipelineRunner, summarize_error


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


def test_pipeline_runner_forces_utf8_child_output(monkeypatch) -> None:
    captured = {}

    class FakeProcess:
        stdout: list[str] = []

        def wait(self) -> int:
            return 0

    def fake_popen(*args, **kwargs):
        captured["env"] = kwargs["env"]
        return FakeProcess()

    monkeypatch.setattr("pose2sim_pipeline_gui.runner.subprocess.Popen", fake_popen)

    result = PipelineRunner(python_path=Path("python.exe"))._run(["reports", "--project-dir", "project"])

    assert result.ok
    assert captured["env"]["PYTHONIOENCODING"] == "utf-8"
