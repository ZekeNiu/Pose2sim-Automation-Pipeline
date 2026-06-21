from __future__ import annotations

import sys
from types import SimpleNamespace
from pathlib import Path

import pytest

from pose2sim_pipeline_gui.checkerboard import generate_checkerboard
from pose2sim_pipeline_gui.paths import GENERATED_CHECKERBOARD_DIR, assert_under_workspace, sanitize_project_name
from pose2sim_pipeline_gui.video import (
    build_normalize_command,
    extract_calibration_video_frames,
    should_extract_calibration_frame,
)


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


def test_extract_calibration_video_frames_uses_official_frame_numbers(monkeypatch, tmp_path: Path) -> None:
    video_path = tmp_path / "cam01_intrinsics.mp4"
    video_path.write_bytes(b"fake video")

    class FakeCapture:
        def __init__(self, path: str):
            self.path = path
            self.index = 0
            self.released = False

        def isOpened(self) -> bool:
            return not self.released

        def get(self, prop: int) -> float:
            return 60.0

        def read(self):
            if self.index > 120:
                return False, None
            frame = f"frame-{self.index}"
            self.index += 1
            return True, frame

        def release(self) -> None:
            self.released = True

    def fake_imwrite(path: str, frame: str) -> bool:
        Path(path).write_text(frame, encoding="utf-8")
        return True

    fake_cv2 = SimpleNamespace(CAP_PROP_FPS=5, VideoCapture=FakeCapture, imwrite=fake_imwrite)
    monkeypatch.setitem(sys.modules, "cv2", fake_cv2)

    frames = extract_calibration_video_frames(video_path, extract_every_N_sec=1, overwrite=False)

    assert [path.name for path in frames] == [
        "cam01_intrinsics_00000.png",
        "cam01_intrinsics_00060.png",
        "cam01_intrinsics_00120.png",
    ]
    assert should_extract_calibration_frame(60, 60, 1) is True
    assert should_extract_calibration_frame(61, 60, 1) is False


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
