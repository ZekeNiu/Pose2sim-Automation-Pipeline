from __future__ import annotations

import os
import subprocess
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .paths import SPORTS3D_PYTHON, WORKSPACE_ROOT


LogCallback = Callable[[str], None]


@dataclass(frozen=True)
class RunResult:
    return_code: int
    tail_lines: list[str]
    error_summary: str | None = None

    @property
    def ok(self) -> bool:
        return self.return_code == 0


def summarize_error(lines: list[str], return_code: int) -> str | None:
    if return_code == 0:
        return None
    for line in reversed(lines):
        stripped = line.strip()
        if not stripped:
            continue
        lowered = stripped.lower()
        if any(token in lowered for token in ["error", "exception", "traceback", "failed"]):
            return stripped
        if any(token in stripped for token in ["错误", "失败", "找不到", "未找到", "异常"]):
            return stripped
    return f"子进程退出码 {return_code}，请查看运行日志末尾。"


class PipelineRunner:
    def __init__(self, python_path: Path = SPORTS3D_PYTHON):
        self.python_path = python_path

    def _run(self, args: list[str], on_log: LogCallback | None = None) -> RunResult:
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        process = subprocess.Popen(
            [str(self.python_path), "-m", "pose2sim_pipeline_gui.pipeline_cli", *args],
            cwd=str(WORKSPACE_ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert process.stdout is not None
        tail: deque[str] = deque(maxlen=80)
        for line in process.stdout:
            clean_line = line.rstrip()
            tail.append(clean_line)
            if on_log:
                on_log(clean_line)
        return_code = process.wait()
        tail_lines = list(tail)
        return RunResult(
            return_code=return_code,
            tail_lines=tail_lines,
            error_summary=summarize_error(tail_lines, return_code),
        )

    def run_all(self, project_dir: Path, skip_synchronization: bool, on_log: LogCallback | None = None) -> RunResult:
        args = ["run", "--project-dir", str(project_dir)]
        if skip_synchronization:
            args.append("--skip-synchronization")
        return self._run(args, on_log)

    def run_steps(
        self,
        project_dir: Path,
        steps: list[str],
        skip_synchronization: bool,
        on_log: LogCallback | None = None,
    ) -> RunResult:
        args = ["run", "--project-dir", str(project_dir), "--steps", *steps]
        if skip_synchronization:
            args.append("--skip-synchronization")
        return self._run(args, on_log)

    def generate_reports(self, project_dir: Path, on_log: LogCallback | None = None) -> RunResult:
        return self._run(["reports", "--project-dir", str(project_dir)], on_log)
