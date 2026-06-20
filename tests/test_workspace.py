from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from pose2sim_pipeline_gui.models import PipelineSettings
from pose2sim_pipeline_gui.paths import PROJECTS_DIR
from pose2sim_pipeline_gui.workspace import ProjectWorkspace


def test_workspace_protects_existing_config_and_backs_up() -> None:
    workspace = ProjectWorkspace("_test_workspace_protection")
    shutil.rmtree(workspace.project_dir, ignore_errors=True)
    try:
        workspace.create()
        (workspace.project_dir / "Config.toml").write_text("[project]\nmulti_person=false\n", encoding="utf-8")

        with pytest.raises(FileExistsError):
            workspace.write_config(PipelineSettings(project_name=workspace.name), overwrite=False)

        workspace.write_config(PipelineSettings(project_name=workspace.name), overwrite=True, backup=True)

        assert (workspace.project_dir / "Config.toml").exists()
        assert list(workspace.project_dir.glob("Config.backup_*.toml"))
    finally:
        shutil.rmtree(workspace.project_dir, ignore_errors=True)
        shutil.rmtree(workspace.output_dir, ignore_errors=True)


def test_workspace_imports_calibration_images_without_ffmpeg(tmp_path: Path) -> None:
    workspace = ProjectWorkspace("_test_workspace_images")
    shutil.rmtree(workspace.project_dir, ignore_errors=True)
    source = tmp_path / "calib.png"
    source.write_bytes(b"fake image bytes")
    try:
        outputs = workspace.import_extrinsics([source])

        assert outputs[0].suffix == ".png"
        assert outputs[0].exists()
        assert workspace.calibration_extension("extrinsics") == "png"
    finally:
        shutil.rmtree(workspace.project_dir, ignore_errors=True)
        shutil.rmtree(workspace.output_dir, ignore_errors=True)
