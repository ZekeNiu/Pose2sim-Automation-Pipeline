from __future__ import annotations

from pathlib import Path

import pytest

from pose2sim_pipeline_gui.checkerboard import generate_checkerboard
from pose2sim_pipeline_gui.paths import GENERATED_CHECKERBOARD_DIR, assert_under_workspace, sanitize_project_name
from pose2sim_pipeline_gui.video import build_normalize_command


def test_sanitize_project_name_blocks_windows_path_separators() -> None:
    assert sanitize_project_name("  squat:trial/01  ") == "squat_trial_01"


def test_assert_under_workspace_rejects_external_path() -> None:
    with pytest.raises(ValueError):
        assert_under_workspace(Path("C:/Windows"))


def test_build_normalize_command_outputs_browser_compatible_mp4(tmp_path: Path) -> None:
    command = build_normalize_command(tmp_path / "in.mov", tmp_path / "out.mp4")
    joined = " ".join(command)
    assert "libx264" in joined
    assert "yuv420p" in joined
    assert "+faststart" in joined


def test_generate_checkerboard_assets() -> None:
    png, pdf = generate_checkerboard(output_dir=GENERATED_CHECKERBOARD_DIR)
    try:
        assert png.exists()
        assert pdf.exists()
    finally:
        png.unlink(missing_ok=True)
        pdf.unlink(missing_ok=True)


def test_generate_a3_extrinsics_checkerboard_assets() -> None:
    png, pdf = generate_checkerboard(
        output_dir=GENERATED_CHECKERBOARD_DIR,
        page_size="A3",
        purpose="extrinsics",
        square_size_mm=45,
    )
    try:
        assert png.exists()
        assert pdf.exists()
        assert "extrinsics_A3" in png.name
    finally:
        png.unlink(missing_ok=True)
        pdf.unlink(missing_ok=True)
