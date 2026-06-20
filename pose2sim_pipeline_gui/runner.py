from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Callable

from .paths import SPORTS3D_PYTHON, WORKSPACE_ROOT


LogCallback = Callable[[str], None]


class PipelineRunner:
    def __init__(self, python_path: Path = SPORTS3D_PYTHON):
        self.python_path = python_path

    def _run(self, args: list[str], on_log: LogCallback | None = None) -> int:
        process = subprocess.Popen(
            [str(self.python_path), "-m", "pose2sim_pipeline_gui.pipeline_cli", *args],
            cwd=str(WORKSPACE_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert process.stdout is not None
        for line in process.stdout:
            if on_log:
                on_log(line.rstrip())
        return process.wait()

    def run_all(self, project_dir: Path, skip_synchronization: bool, on_log: LogCallback | None = None) -> int:
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
    ) -> int:
        args = ["run", "--project-dir", str(project_dir), "--steps", *steps]
        if skip_synchronization:
            args.append("--skip-synchronization")
        return self._run(args, on_log)

    def generate_reports(self, project_dir: Path, on_log: LogCallback | None = None) -> int:
        return self._run(["reports", "--project-dir", str(project_dir)], on_log)
