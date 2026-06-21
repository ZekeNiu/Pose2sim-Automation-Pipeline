from __future__ import annotations

import json
import subprocess
import sys
from types import ModuleType, SimpleNamespace
from pathlib import Path

from pose2sim_pipeline_gui.environment import (
    check_environment,
    pose2sim_intrinsics_video_extraction_bug_present,
    summarize_pose2sim_update,
)


class _Completed:
    stdout = ""


def test_pose2sim_intrinsics_bug_detection_uses_extract_frames_source(monkeypatch) -> None:
    fake_pose2sim = ModuleType("Pose2Sim")
    fake_calibration = SimpleNamespace(extract_frames=object())
    fake_pose2sim.calibration = fake_calibration
    monkeypatch.setitem(sys.modules, "Pose2Sim", fake_pose2sim)
    monkeypatch.setattr(
        "pose2sim_pipeline_gui.environment.inspect.getsource",
        lambda obj: "Path(Path(video_path).exists().stem + '_00000.png')",
    )

    assert pose2sim_intrinsics_video_extraction_bug_present() is True


def test_environment_checks_gui_runtime_dependencies(monkeypatch, tmp_path: Path) -> None:
    python_path = tmp_path / "python.exe"
    python_path.write_text("fake", encoding="utf-8")
    data = {
        "python": str(python_path),
        "python_version": "3.11.9",
        "python_version_info": [3, 11, 9],
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
    assert not any("0.10.43" in warning for warning in status.warnings)


def test_environment_warns_when_python_310_cannot_install_new_pose2sim(monkeypatch, tmp_path: Path) -> None:
    python_path = tmp_path / "python.exe"
    python_path.write_text("fake", encoding="utf-8")
    data = {
        "python": str(python_path),
        "python_version": "3.10.20",
        "python_version_info": [3, 10, 20],
        "pose2sim": "0.10.43",
        "opensim": "4.5.1",
        "customtkinter": "5.2.2",
        "plotly": "6.8.0",
        "openpyxl": "3.1.5",
        "pandas": "2.2.3",
        "pillow": "11.0.0",
        "toml": "0.10.2",
        "gpu_hint": "CPU",
    }

    def fake_run(*args, **kwargs):
        completed = _Completed()
        completed.stdout = json.dumps(data, ensure_ascii=False)
        return completed

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr("pose2sim_pipeline_gui.environment.shutil.which", lambda name: f"{name}.exe")

    status = check_environment(python_path)
    message, is_error = summarize_pose2sim_update(status, 0)

    assert not status.errors
    assert any("Python >= 3.11" in warning for warning in status.warnings)
    assert any("0.10.47" in warning for warning in status.warnings)
    assert is_error is True
    assert "不支持 Pose2Sim 0.10.44+" in message
