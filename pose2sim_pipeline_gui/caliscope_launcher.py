from __future__ import annotations

import argparse
import os
import sys
import traceback
from pathlib import Path

from .caliscope_bridge import seed_caliscope_recent_project


def _launch_direct(workspace_dir: Path) -> None:
    os.environ.setdefault("QT_API", "pyside6")

    from PySide6.QtWidgets import QApplication

    from caliscope.gui.gc_confinement import disable, enable
    from caliscope.gui.main_widget import MainWindow
    from caliscope.logger import setup_logging
    from caliscope.startup import initialize_app
    from caliscope.trackers import tracker_registry
    from caliscope import MODELS_DIR
    from caliscope.__main__ import _seed_default_model_cards

    setup_logging()
    initialize_app()
    _seed_default_model_cards(MODELS_DIR)
    tracker_registry.scan_onnx_models(MODELS_DIR)

    app = QApplication([sys.argv[0]])
    gc_timer = enable()
    window = MainWindow()
    window.show()
    window.launch_workspace(str(workspace_dir))
    app.exec()
    disable(gc_timer)


def _launch_cli_fallback(workspace_dir: Path) -> None:
    seed_caliscope_recent_project(workspace_dir)
    from caliscope.__main__ import CLI_parser

    sys.argv = [sys.argv[0]]
    CLI_parser()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Launch Caliscope for a Pose2Sim GUI project workspace.")
    parser.add_argument("--workspace", required=True)
    args = parser.parse_args(argv)
    workspace_dir = Path(args.workspace).resolve()
    workspace_dir.mkdir(parents=True, exist_ok=True)
    seed_caliscope_recent_project(workspace_dir)

    try:
        _launch_direct(workspace_dir)
        return 0
    except Exception:
        traceback.print_exc()
        try:
            _launch_cli_fallback(workspace_dir)
            return 0
        except Exception:
            traceback.print_exc()
            return 1


if __name__ == "__main__":
    raise SystemExit(main())
