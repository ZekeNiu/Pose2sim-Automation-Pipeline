from __future__ import annotations

import json
import subprocess
from pathlib import Path

from pose2sim_pipeline_gui.environment import check_environment


class _Completed:
    stdout = ""


def test_environment_checks_gui_runtime_dependencies(monkeypatch, tmp_path: Path) -> None:
    python_path = tmp_path / "python.exe"
    python_path.write_text("fake", encoding="utf-8")
    data = {
        "python": str(python_path),
        "pose2sim": "0.10.47",
        "opensim": "4.5.1",
        "customtkinter": "5.2.2",
        "plotly": "6.8.0",
        "openpyxl": "3.1.5",
        "pandas": None,
        "pillow": None,
        "toml": None,
        "gpu_hint": "CPU",
    }

    def fake_run(*args, **kwargs):
        completed = _Completed()
        completed.stdout = json.dumps(data, ensure_ascii=False)
        return completed

    def fake_which(name: str):
        if name == "ffmpeg":
            return "ffmpeg.exe"
        return None

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr("pose2sim_pipeline_gui.environment.shutil.which", fake_which)

    status = check_environment(python_path)

    assert "缺少 pandas。" in status.errors
    assert "缺少 Pillow。" in status.errors
    assert "缺少 toml。" in status.errors
    assert any("ffprobe" in warning for warning in status.warnings)
    assert any("0.10.43" in warning for warning in status.warnings)
