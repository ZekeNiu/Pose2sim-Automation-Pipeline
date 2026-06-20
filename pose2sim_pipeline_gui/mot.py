from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass
class MotData:
    path: Path
    in_degrees: bool
    frame: pd.DataFrame


def read_mot(path: Path) -> MotData:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    try:
        end_idx = next(i for i, line in enumerate(lines) if line.strip().lower() == "endheader")
    except StopIteration as exc:
        raise ValueError(f"不是有效的 OpenSim .mot 文件: {path}") from exc
    in_degrees = any("indegrees=yes" in line.replace(" ", "").lower() for line in lines[:end_idx])
    header_idx = end_idx + 1
    if header_idx >= len(lines):
        raise ValueError(f".mot 文件缺少列名: {path}")
    columns = lines[header_idx].split()
    data = pd.read_csv(
        path,
        sep=r"\s+",
        skiprows=header_idx + 1,
        names=columns,
        engine="python",
    )
    return MotData(path=path, in_degrees=in_degrees, frame=data)


TRANSLATION_SUFFIXES = ("_tx", "_ty", "_tz", "_t1", "_t2", "_t3")


def angle_columns(frame: pd.DataFrame) -> list[str]:
    columns: list[str] = []
    for column in frame.columns:
        lower = column.lower()
        if lower == "time":
            continue
        if lower.endswith(TRANSLATION_SUFFIXES):
            continue
        if lower in {"abs_t1", "abs_t2", "abs_t3"}:
            continue
        columns.append(column)
    return columns

