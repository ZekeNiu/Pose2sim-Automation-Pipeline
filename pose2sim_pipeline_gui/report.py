from __future__ import annotations

import html
import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

from .joint_metadata import is_supported_joint_column, metadata_for, ordered_columns
from .mot import angle_columns, read_mot
from .paths import assert_under_workspace
from .results_export import export_pose2sim_outputs


@dataclass(frozen=True)
class QualityDiagnostic:
    confidence: str
    summary: str
    sections: dict[str, list[str]]
    table: pd.DataFrame


@dataclass(frozen=True)
class ReportVideo:
    source: Path
    media_name: str
    label: str
    source_type: str
    note: str = ""


def _read_sto_table(path: Path) -> pd.DataFrame:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    try:
        end_idx = next(i for i, line in enumerate(lines) if line.strip().lower() == "endheader")
    except StopIteration:
        return pd.DataFrame()
    columns = lines[end_idx + 1].split()
    return pd.read_csv(path, sep=r"\s+", skiprows=end_idx + 2, names=columns, engine="python")


def _numbers_from_brackets(text: str) -> list[float]:
    match = re.search(r"\[([^\]]+)\]", text)
    if not match:
        return []
    return [float(value) for value in re.findall(r"-?\d+(?:\.\d+)?", match.group(1))]


def _score_label(scores: list[int]) -> str:
    if not scores:
        return "未知"
    worst = max(scores)
    if worst >= 3:
        return "低"
    if worst == 2:
        return "中"
    return "高"


def _score_grade(score: int) -> str:
    if score <= 1:
        return "正常"
    if score == 2:
        return "谨慎"
    return "低可信"


def _add_quality_check(
    *,
    sections: dict[str, list[str]],
    rows: list[dict[str, str | float]],
    risk_scores: list[int],
    category: str,
    metric: str,
    current: str,
    good_range: str,
    caution_range: str,
    score: int,
    explanation: str,
    suggestion: str,
) -> None:
    grade = _score_grade(score)
    line = (
        f"{metric}：当前值 {current}；合理区间：{good_range}；谨慎区间：{caution_range}；"
        f"判定：{grade}。{explanation} 建议：{suggestion}"
    )
    sections.setdefault(category, []).append(line)
    rows.append(
        {
            "类别": category,
            "指标": metric,
            "当前值": current,
            "合理区间": good_range,
            "谨慎区间": caution_range,
            "等级": grade,
            "解释": explanation,
            "建议": suggestion,
        }
    )
    risk_scores.append(score)


def _parse_quality_diagnostics(project_dir: Path) -> QualityDiagnostic:
    sections: dict[str, list[str]] = {
        "校准": [],
        "同步": [],
        "人物匹配": [],
        "三维重建": [],
        "逆运动学": [],
        "缺失/插值": [],
        "OpenSim 查看": [],
        "解释建议": [],
    }
    rows: list[dict[str, str | float]] = []
    risk_scores: list[int] = []
    log_path = project_dir / "logs.txt"
    if log_path.exists():
        text = log_path.read_text(encoding="utf-8", errors="replace")
        intrinsics_matches = [float(value) for value in re.findall(r"Intrinsics error:\s*([0-9.]+)\s*px", text)]
        if intrinsics_matches:
            max_value = max(intrinsics_matches)
            score = 1 if max_value <= 0.5 else 2 if max_value <= 1.0 else 3
            _add_quality_check(
                sections=sections,
                rows=rows,
                risk_scores=risk_scores,
                category="校准",
                metric="内参 RMS",
                current=", ".join(f"{value:.3g} px" for value in intrinsics_matches),
                good_range="≤0.5 px",
                caution_range="0.5-1.0 px",
                score=score,
                explanation="内参描述镜头畸变和焦距，误差越低越有利于后续三维重建。",
                suggestion="若超过 1.0 px，重新录制清晰、不同位置和不同角度的棋盘格内参视频。",
            )

        residual_matches = re.findall(
            r"Residual \(RMS\) calibration errors.*?\[([^\]]+)\]\s*px.*?corresponds to\s*\[([^\]]+)\]\s*mm",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if residual_matches:
            px_values = [float(value) for value in re.findall(r"-?\d+(?:\.\d+)?", residual_matches[-1][0])]
            mm_values = [float(value) for value in re.findall(r"-?\d+(?:\.\d+)?", residual_matches[-1][1])]
            if px_values:
                max_px = max(px_values)
                max_mm = max(mm_values) if mm_values else float("inf")
                score = 1 if max_px <= 5 or max_mm <= 15 else 2 if max_px <= 15 or max_mm <= 30 else 3
                current = ", ".join(f"{value:.3g} px" for value in px_values)
                if mm_values:
                    current += "；" + ", ".join(f"{value:.3g} mm" for value in mm_values)
                _add_quality_check(
                    sections=sections,
                    rows=rows,
                    risk_scores=risk_scores,
                    category="校准",
                    metric="外参/校准 RMS",
                    current=current,
                    good_range="≤5 px 或 ≤15 mm",
                    caution_range="5-15 px 或 15-30 mm",
                    score=score,
                    explanation="外参决定每台相机在三维空间中的位置和朝向。",
                    suggestion="点集中在小棋盘格或画面边缘时，优先改用分布更大的场景点，或使用更大棋盘格并让其覆盖更多运动空间。",
                )
        else:
            residual_line_matches = re.findall(r"Residual \(RMS\) calibration errors.*", text, flags=re.IGNORECASE)
            if residual_line_matches:
                values = _numbers_from_brackets(residual_line_matches[-1])
                if values:
                    max_value = max(values)
                    score = 1 if max_value <= 5 else 2 if max_value <= 15 else 3
                    _add_quality_check(
                        sections=sections,
                        rows=rows,
                        risk_scores=risk_scores,
                        category="校准",
                        metric="外参/校准 RMS",
                        current=", ".join(f"{value:.3g} px" for value in values),
                        good_range="≤5 px 或 ≤15 mm",
                        caution_range="5-15 px 或 15-30 mm",
                        score=score,
                        explanation="外参决定每台相机在三维空间中的位置和朝向。",
                        suggestion="检查棋盘格/场景点是否清晰、分布是否充分，必要时重做外参。",
                    )

        sync_matches = re.findall(r"Camera .*? correlation [0-9.]+", text, flags=re.IGNORECASE)
        if sync_matches:
            correlations: list[float] = []
            offsets: list[str] = []
            for line in sync_matches[-8:]:
                corr_match = re.search(r"correlation ([0-9]+(?:\.[0-9]+)?)", line, flags=re.IGNORECASE)
                offset_match = re.search(r": ([+-]?\d+) frames offset", line, flags=re.IGNORECASE)
                if corr_match:
                    correlations.append(float(corr_match.group(1)))
                if offset_match:
                    offsets.append(offset_match.group(1))
            if correlations:
                min_corr = min(correlations)
                score = 1 if min_corr >= 0.8 else 2 if min_corr >= 0.5 else 3
                msg = f"同步相关系数范围 {min(correlations):.2f}-{max(correlations):.2f}，帧偏移约为 {', '.join(offsets) if offsets else '未解析'} 帧。"
                _add_quality_check(
                    sections=sections,
                    rows=rows,
                    risk_scores=risk_scores,
                    category="同步",
                    metric="相关系数/帧偏移",
                    current=msg,
                    good_range="相关系数 ≥0.8",
                    caution_range="相关系数 0.5-0.8",
                    score=score,
                    explanation="相关系数越高，说明不同机位识别到的同步动作越一致。",
                    suggestion="相关系数偏低时，录制更明显的同步动作，或开启官方手动选人/同步窗口确认人员和关键点。",
                )

        association_matches = re.findall(
            r"Mean reprojection error for (.*?) point on all frames is ([0-9.]+) px.*?corresponds to ([0-9.]+) mm",
            text,
            flags=re.IGNORECASE,
        )
        if association_matches:
            keypoint, px_text, mm_text = association_matches[-1]
            px = float(px_text)
            mm = float(mm_text)
            score = 1 if px <= 20 else 2 if px <= 35 else 3
            _add_quality_check(
                sections=sections,
                rows=rows,
                risk_scores=risk_scores,
                category="人物匹配",
                metric=f"{keypoint} 单人关联误差",
                current=f"{px:.2f} px / {mm:.1f} mm",
                good_range="≤20 px",
                caution_range="20-35 px",
                score=score,
                explanation="单人模式仍需要确认每个机位跟踪的是同一个人，同一关键点重投影误差越低越可靠。",
                suggestion="误差偏高时，换更稳定的跟踪参考点，减少遮挡，或开启官方手动选人/同步窗口。",
            )

        reprojection_summary = re.findall(
            r"Mean reprojection error for all points.*? is ([0-9.]+) px.*?(?:corresponds to|~) ([0-9.]+) (mm|m)",
            text,
            flags=re.IGNORECASE,
        )
        if reprojection_summary:
            px_text, distance_text, distance_unit = reprojection_summary[-1]
            px = float(px_text)
            distance = float(distance_text)
            score = 1 if px <= 8 else 2 if px <= 15 else 3
            _add_quality_check(
                sections=sections,
                rows=rows,
                risk_scores=risk_scores,
                category="三维重建",
                metric="平均重投影误差",
                current=f"{px:.2f} px / {distance:.3g} {distance_unit}",
                good_range="≤8 px",
                caution_range="8-15 px",
                score=score,
                explanation="三维重建误差反映 2D 关键点、相机标定和多视角几何是否一致。",
                suggestion="误差偏高时，优先检查外参、相机顺序、遮挡和关键点识别质量。",
            )
        excluded_matches = re.findall(r"In average, ([0-9.]+) cameras had to be excluded", text, flags=re.IGNORECASE)
        if excluded_matches:
            excluded = float(excluded_matches[-1])
            score = 1 if excluded <= 0.2 else 2 if excluded <= 0.8 else 3
            _add_quality_check(
                sections=sections,
                rows=rows,
                risk_scores=risk_scores,
                category="三维重建",
                metric="平均排除相机数",
                current=f"{excluded:.2f} 台/帧",
                good_range="≤0.2 台/帧",
                caution_range="0.2-0.8 台/帧",
                score=score,
                explanation="排除相机越多，说明某些机位关键点质量或几何一致性越不稳定。",
                suggestion="排除偏多时，检查被排除机位的遮挡、曝光、相机顺序和标定。",
            )

    ik_files = sorted((project_dir / "kinematics").glob("*marker_errors*.sto"))
    if not ik_files:
        ik_files = sorted((project_dir / "kinematics").glob("_ik_marker_errors.sto"))
    for ik_file in ik_files:
        table = _read_sto_table(ik_file)
        if not table.empty and "marker_error_RMS" in table:
            mean_rms = float(table["marker_error_RMS"].mean())
            max_err = float(table.get("marker_error_max", pd.Series(dtype=float)).max())
            score = 1 if mean_rms <= 0.02 else 2 if mean_rms <= 0.04 else 3
            _add_quality_check(
                sections=sections,
                rows=rows,
                risk_scores=risk_scores,
                category="逆运动学",
                metric="IK marker error",
                current=f"RMS {mean_rms:.4f} m / max {max_err:.4f} m",
                good_range="RMS ≤0.02 m",
                caution_range="RMS 0.02-0.04 m",
                score=score,
                explanation="IK marker error 表示 OpenSim 模型标记点与三维重建标记点的拟合距离。",
                suggestion="超过 0.04 m 时，关节角主要看大趋势；优先改善外参、遮挡、跟踪参考点和 OpenSim 缩放输入身高。",
            )

    trc_files = sorted((project_dir / "pose-3d").glob("*.trc"))
    for trc_file in trc_files[:3]:
        text = trc_file.read_text(encoding="utf-8", errors="replace")
        nan_count = text.lower().count("nan")
        if nan_count:
            _add_quality_check(
                sections=sections,
                rows=rows,
                risk_scores=risk_scores,
                category="缺失/插值",
                metric="TRC 缺失值",
                current=f"{nan_count} 个 NaN",
                good_range="0 个 NaN",
                caution_range="少量、非关键时段 NaN",
                score=2,
                explanation="NaN 表示部分关键点在部分帧没有可用三维坐标。",
                suggestion="如果 NaN 集中在动作峰值附近，相关关节角峰值需要谨慎解释。",
            )

    confidence = _score_label(risk_scores)
    if confidence == "高":
        summary = "综合置信度：高。当前可解析指标整体较稳定，适合查看关节活动度趋势和主要峰值。"
    elif confidence == "中":
        summary = "综合置信度：中。结果可用于动作趋势分析，但小幅差异和快速峰值需要结合视频与完整诊断谨慎解释。"
    elif confidence == "低":
        summary = "综合置信度：低。建议优先检查校准、同步、遮挡和关键点识别后再解释关节角。"
    else:
        summary = "综合置信度：未知。未解析到足够质量指标，请同时查看 Pose2Sim 原始日志、叠加视频和 OpenSim 输出。"

    sections["OpenSim 查看"].append(
        "查看 OpenSim 动画时，先打开 kinematics 目录下的 .osim 模型，再在 OpenSim 中加载同名 .mot 文件。"
        "如果没有骨架外观，请确认 kinematics/Geometry 目录已随输出一起复制。"
    )
    sections["OpenSim 查看"].append(
        "模型失真通常不是 .mot 文件缺失导致，更常见原因是外参覆盖不足、IK marker error 偏高、遮挡、相机视角太少或身高/尺度输入不准。"
    )
    sections["解释建议"].append(
        "叠加检测视频里的 2D 骨架稳定，不等于三维结果和 OpenSim 动作可信；"
        "若外参 RMS、人物匹配误差或 IK marker error 超出合理区间，应优先重做外参。"
    )
    sections["解释建议"].append("本报告只解释数据质量和关节活动度趋势，不构成医学诊断或康复处方。")
    if not rows:
        rows.append(
            {
                "类别": "诊断",
                "指标": "未解析",
                "当前值": "未知",
                "合理区间": "未知",
                "谨慎区间": "未知",
                "等级": "未知",
                "解释": summary,
                "建议": "查看 Pose2Sim 原始日志、叠加视频和 OpenSim 输出。",
            }
        )
    return QualityDiagnostic(confidence=confidence, summary=summary, sections=sections, table=pd.DataFrame(rows))


def _select_report_video_sources(project_dir: Path) -> list[ReportVideo]:
    overlay_videos = sorted((project_dir / "pose").glob("*_pose.mp4"))
    if overlay_videos:
        return [
            ReportVideo(
                source=path,
                media_name=path.name,
                label=path.stem.replace("_pose", ""),
                source_type="叠加检测视频",
            )
            for path in overlay_videos
        ]
    return [
        ReportVideo(source=path, media_name=path.name, label=path.stem, source_type="规范化原始视频")
        for path in sorted((project_dir / "videos").glob("*.mp4"))
    ]


def _is_browser_compatible_video(path: Path) -> bool | None:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return None
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=codec_name,pix_fmt",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        return None
    try:
        data = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        return None
    stream = (data.get("streams") or [{}])[0]
    return stream.get("codec_name") == "h264" and stream.get("pix_fmt") == "yuv420p"


def _transcode_video_for_browser(source: Path, target: Path) -> bool:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return False
    temp_target = target.with_name(f"{target.stem}.tmp{target.suffix}")
    temp_target.unlink(missing_ok=True)
    result = subprocess.run(
        [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-i",
            str(source),
            "-map",
            "0:v:0",
            "-an",
            "-vf",
            "scale=trunc(iw/2)*2:trunc(ih/2)*2",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "23",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(temp_target),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0 or not temp_target.exists():
        temp_target.unlink(missing_ok=True)
        return False
    target.unlink(missing_ok=True)
    temp_target.replace(target)
    return True


def _copy_report_videos(project_dir: Path, media_dir: Path) -> list[ReportVideo]:
    media_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[ReportVideo] = []
    for video in _select_report_video_sources(project_dir):
        target = media_dir / video.media_name
        compatible = _is_browser_compatible_video(video.source)
        source_type = video.source_type
        note = ""
        if compatible is False:
            if _transcode_video_for_browser(video.source, target):
                source_type = f"{source_type}，已转为浏览器兼容视频"
            else:
                shutil.copy2(video.source, target)
                note = "未能转为 H.264，若浏览器无法播放，请用播放器打开 media 文件。"
        else:
            shutil.copy2(video.source, target)
            if compatible is None:
                note = "未能确认浏览器兼容性。"
        outputs.append(
            ReportVideo(
                source=target,
                media_name=target.name,
                label=video.label,
                source_type=source_type,
                note=note,
            )
        )
    return outputs


def _build_figure(frame: pd.DataFrame, columns: list[str], title: str) -> go.Figure:
    fig = go.Figure()
    for column in columns:
        meta = metadata_for(column)
        fig.add_trace(
            go.Scatter(
                x=frame["time"],
                y=frame[column],
                mode="lines",
                name=meta.zh,
                hovertemplate=f"{meta.zh}: %{{y:.2f}}°<extra></extra>",
            )
        )
    fig.update_layout(
        title=title,
        xaxis_title="时间 (秒)",
        yaxis_title="角度 (°)",
        hovermode="x unified",
        template="plotly_white",
        legend={"orientation": "h", "y": -0.25},
        margin={"l": 60, "r": 20, "t": 60, "b": 120},
    )
    return fig


def _stats_table(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for column in columns:
        meta = metadata_for(column)
        series = frame[column]
        rows.append(
            {
                "指标": meta.zh,
                "OpenSim列名": column,
                "最小值(°)": round(float(series.min()), 3),
                "最大值(°)": round(float(series.max()), 3),
                "平均值(°)": round(float(series.mean()), 3),
                "活动范围ROM(°)": round(float(series.max() - series.min()), 3),
                "运动平面": meta.plane,
                "0°/中立位": meta.neutral,
                "数值方向": meta.direction,
                "计算定义": meta.definition,
                "解释边界": meta.boundary,
            }
        )
    return pd.DataFrame(rows)


def _mot_label(path: Path, index: int, total: int) -> str:
    stem = path.stem
    person_match = re.search(r"(?:^|[_-])(P\d+|person\d+)(?:$|[_-])", stem, flags=re.IGNORECASE)
    if person_match:
        return person_match.group(1).upper().replace("PERSON", "人员 ")
    if total == 1:
        return stem
    return f"结果 {index}: {stem}"


def _safe_sheet_name(name: str) -> str:
    cleaned = re.sub(r"[\[\]\*\?/\\:]", "_", name)
    return cleaned[:31] or "Sheet"


def _definition_payload(stats: pd.DataFrame, prefix: str) -> dict[str, dict[str, str]]:
    payload: dict[str, dict[str, str]] = {}
    for _, row in stats.iterrows():
        key = f"{prefix}::{row['指标']}"
        payload[key] = {
            "plane": str(row["运动平面"]),
            "neutral": str(row["0°/中立位"]),
            "direction": str(row["数值方向"]),
            "definition": str(row["计算定义"]),
            "boundary": str(row["解释边界"]),
        }
    return payload


def _table_rows(stats: pd.DataFrame, prefix: str) -> str:
    return "\n".join(
        "<tr>"
        f"<td>{html.escape(str(row['指标']))} <button class='info' data-key='{html.escape(prefix)}::{html.escape(str(row['指标']))}'>i</button></td>"
        f"<td>{row['最小值(°)']}</td><td>{row['最大值(°)']}</td><td>{row['平均值(°)']}</td><td>{row['活动范围ROM(°)']}</td>"
        "</tr>"
        for _, row in stats.iterrows()
    )


def generate_reports(project_dir: Path, output_dir: Path) -> tuple[Path, Path]:
    assert_under_workspace(project_dir)
    assert_under_workspace(output_dir)
    reports_dir = output_dir / "reports"
    media_dir = reports_dir / "media"
    reports_dir.mkdir(parents=True, exist_ok=True)
    mot_files = sorted((project_dir / "kinematics").glob("*.mot"))
    if not mot_files:
        raise FileNotFoundError(f"未找到 .mot 关节角度文件: {project_dir / 'kinematics'}")

    videos = _copy_report_videos(project_dir, media_dir)
    diagnostics = _parse_quality_diagnostics(project_dir)
    definitions_payload: dict[str, dict[str, str]] = {}
    subject_blocks: list[str] = []
    selector_options: list[str] = []
    hidden_messages: list[str] = []
    first_excel_path = reports_dir / f"{project_dir.name}_关节活动度.xlsx"

    with pd.ExcelWriter(first_excel_path, engine="openpyxl") as writer:
        for index, mot_path in enumerate(mot_files, start=1):
            mot = read_mot(mot_path)
            raw_columns = angle_columns(mot.frame)
            columns = ordered_columns([column for column in raw_columns if is_supported_joint_column(column)])
            hidden_count = len(raw_columns) - len(columns)
            if hidden_count:
                hidden_messages.append(f"{mot_path.name} 已隐藏 {hidden_count} 个辅助坐标或未知指标。")
            if not columns:
                raise ValueError(f".mot 文件中没有可报告的已知关节活动度列: {mot.path}")

            label = _mot_label(mot_path, index, len(mot_files))
            block_id = f"subject-{index}"
            report_frame = mot.frame[["time", *columns]].copy()
            stats = _stats_table(report_frame, columns)
            definitions = stats[
                ["指标", "OpenSim列名", "运动平面", "0°/中立位", "数值方向", "计算定义", "解释边界"]
            ].copy()
            display_frame = report_frame.rename(columns={column: metadata_for(column).zh for column in columns})

            if len(mot_files) == 1:
                display_frame.to_excel(writer, sheet_name="逐帧关节活动度", index=False)
                stats.to_excel(writer, sheet_name="统计摘要", index=False)
                definitions.to_excel(writer, sheet_name="指标定义", index=False)
            else:
                display_frame.to_excel(writer, sheet_name=_safe_sheet_name(f"{label}_逐帧"), index=False)
                stats.to_excel(writer, sheet_name=_safe_sheet_name(f"{label}_统计"), index=False)
                definitions.to_excel(writer, sheet_name=_safe_sheet_name(f"{label}_定义"), index=False)

            definitions_payload.update(_definition_payload(stats, block_id))
            fig = _build_figure(report_frame, columns, f"{label} 关节活动度时间序列")
            chart_html = pio.to_html(
                fig,
                full_html=False,
                include_plotlyjs=True if index == 1 else False,
                div_id=f"joint-chart-{index}",
            )
            selector_options.append(
                f"<option value='{html.escape(block_id)}'>{html.escape(label)}</option>"
            )
            subject_blocks.append(
                f"""
      <section class="subject-block" id="{html.escape(block_id)}">
        <h2>{html.escape(label)}</h2>
        <div class="panel chart-panel">{chart_html}</div>
        <section class="panel">
          <h3>统计表</h3>
          <table>
            <thead><tr><th>指标</th><th>最小值(°)</th><th>最大值(°)</th><th>平均值(°)</th><th>ROM(°)</th></tr></thead>
            <tbody>{_table_rows(stats, block_id)}</tbody>
          </table>
        </section>
      </section>
"""
            )

        diagnostics.table.to_excel(writer, sheet_name="质量诊断", index=False)

    full_diag_html = _diagnostic_sections_html(diagnostics.sections)
    hidden_notice = " ".join(hidden_messages)
    selector_html = ""
    selector_panel_html = ""
    if len(mot_files) > 1:
        selector_html = (
            "<label for='subject-select'>人员/结果：</label>"
            f"<select id='subject-select'>{''.join(selector_options)}</select>"
        )
        selector_panel_html = f'<section class="panel">{selector_html}</section>'
    video_grid = _video_grid(videos)
    html_path = reports_dir / f"{project_dir.name}_关节活动度.html"
    html_path.write_text(
        f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Pose2sim运动学分析报告</title>
  <style>
    body {{ margin: 0; font-family: "Microsoft YaHei", Arial, sans-serif; background: #f6f7f9; color: #1f2933; }}
    header {{ padding: 24px 32px; background: #102033; color: white; }}
    main {{ padding: 24px 32px 48px; max-width: 1440px; margin: 0 auto; }}
    section {{ margin-bottom: 24px; }}
    select {{ padding: 8px 10px; border: 1px solid #b8c2cc; border-radius: 6px; background: white; }}
    .summary {{ background: white; border-left: 5px solid #2563eb; padding: 16px; border-radius: 6px; display: grid; gap: 10px; }}
    .panel {{ background: white; border: 1px solid #dde3ea; border-radius: 8px; padding: 16px; }}
    .notice {{ color: #475569; font-size: 14px; }}
    .video-grid {{ display: grid; gap: 12px; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); }}
    .video-grid.video-count-1 {{ grid-template-columns: minmax(320px, 900px); }}
    .video-grid.video-count-2 {{ grid-template-columns: repeat(2, minmax(260px, 1fr)); }}
    .video-card {{ display: grid; gap: 8px; }}
    .video-card h3 {{ margin: 0; font-size: 15px; }}
    video {{ width: 100%; aspect-ratio: 16 / 9; object-fit: contain; background: #111827; border-radius: 6px; }}
    .chart-panel {{ overflow-x: auto; }}
    table {{ width: 100%; border-collapse: collapse; background: white; }}
    th, td {{ border-bottom: 1px solid #e5e7eb; padding: 10px; text-align: left; font-size: 14px; }}
    th {{ background: #eef2f7; }}
    .info {{ border: 1px solid #93a4b8; border-radius: 50%; width: 20px; height: 20px; cursor: pointer; background: white; color: #2563eb; }}
    .subject-block[hidden] {{ display: none; }}
    dialog {{ border: none; border-radius: 8px; max-width: 760px; padding: 24px; box-shadow: 0 20px 60px rgba(0,0,0,.25); }}
    button.primary {{ background: #2563eb; color: white; border: none; border-radius: 6px; padding: 8px 12px; cursor: pointer; }}
    @media (max-width: 980px) {{ main {{ padding: 16px; }} .video-grid, .video-grid.video-count-2 {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <header>
    <h1>Pose2sim运动学分析报告</h1>
  </header>
  <main>
    <section class="summary">
      <div><strong>质量诊断与解释边界：</strong>{html.escape(diagnostics.summary)}</div>
      <div class="notice">{html.escape(hidden_notice) if hidden_notice else '图表和统计表仅显示已识别的关节活动度指标。'}</div>
      <button class="primary" id="open-diagnostics">查看完整诊断</button>
    </section>
    <section class="panel">
      <h2>同步视频</h2>
      {video_grid or '<p>未找到可嵌入视频。</p>'}
    </section>
    {selector_panel_html}
    {''.join(subject_blocks)}
  </main>
  <dialog id="info-dialog"><h3 id="info-title"></h3><div id="info-body"></div><button class="primary" onclick="this.closest('dialog').close()">关闭</button></dialog>
  <dialog id="diagnostic-dialog"><h3>完整诊断</h3>{full_diag_html}<button class="primary" onclick="this.closest('dialog').close()">关闭</button></dialog>
  <script>
    const definitions = {json.dumps(definitions_payload, ensure_ascii=False)};
    const selector = document.getElementById('subject-select');
    function updateSubject() {{
      const active = selector ? selector.value : 'subject-1';
      document.querySelectorAll('.subject-block').forEach(block => {{
        block.hidden = block.id !== active;
      }});
    }}
    if (selector) selector.addEventListener('change', updateSubject);
    updateSubject();
    const syncedVideos = Array.from(document.querySelectorAll('.sync-video'));
    document.querySelectorAll('[id^="joint-chart-"]').forEach(chart => {{
      chart.on('plotly_hover', (event) => {{
        const t = event.points && event.points.length ? Number(event.points[0].x) : null;
        if (Number.isFinite(t)) {{
          syncedVideos.forEach(v => {{
            if (Math.abs(v.currentTime - t) > 0.15) v.currentTime = Math.max(0, t);
          }});
        }}
      }});
    }});
    document.querySelectorAll('.info').forEach(btn => {{
      btn.addEventListener('click', () => {{
        const key = btn.dataset.key;
        const name = key.split('::').slice(1).join('::');
        const d = definitions[key] || {{}};
        document.getElementById('info-title').textContent = name;
        document.getElementById('info-body').innerHTML =
          `<p><b>运动平面：</b>${{d.plane || ''}}</p>` +
          `<p><b>0°位/中立位：</b>${{d.neutral || ''}}</p>` +
          `<p><b>数值方向：</b>${{d.direction || ''}}</p>` +
          `<p><b>计算定义：</b>${{d.definition || ''}}</p>` +
          `<p><b>解释边界：</b>${{d.boundary || ''}}</p>`;
        document.getElementById('info-dialog').showModal();
      }});
    }});
    document.getElementById('open-diagnostics').addEventListener('click', () => {{
      document.getElementById('diagnostic-dialog').showModal();
    }});
  </script>
</body>
</html>
""",
        encoding="utf-8",
    )
    return html_path, first_excel_path


def _video_grid(videos: list[ReportVideo]) -> str:
    if not videos:
        return ""
    count_class = f"video-count-{min(len(videos), 4)}"
    card_items: list[str] = []
    for video in videos:
        note_html = f"<div class='notice'>{html.escape(video.note)}</div>" if video.note else ""
        card_items.append(
            "<div class='video-card'>"
            f"<h3>{html.escape(video.label)}</h3>"
            f"<video class='sync-video' controls preload='metadata' src='media/{html.escape(video.media_name)}'></video>"
            f"{note_html}"
            "</div>"
        )
    cards = "\n".join(card_items)
    return f"<div class='video-grid {count_class}'>{cards}</div>"


def _diagnostic_sections_html(sections: dict[str, list[str]]) -> str:
    blocks: list[str] = []
    for title, lines in sections.items():
        if not lines:
            continue
        items = "".join(f"<li>{html.escape(line)}</li>" for line in lines)
        blocks.append(f"<section><h4>{html.escape(title)}</h4><ul>{items}</ul></section>")
    return "".join(blocks) or "<p>未发现可解析的完整诊断信息。</p>"


def quality_diagnostics_for_project(project_dir: Path) -> QualityDiagnostic:
    return _parse_quality_diagnostics(project_dir)


def diagnostic_issue_lines(diagnostics: QualityDiagnostic, limit: int = 4) -> list[str]:
    if diagnostics.table.empty:
        return []
    rows = []
    for _, row in diagnostics.table.iterrows():
        grade = str(row.get("等级", ""))
        if grade in {"正常", "未知"}:
            continue
        rows.append(
            f"{row.get('类别', '')} - {row.get('指标', '')}: 当前值 {row.get('当前值', '')}；"
            f"合理区间 {row.get('合理区间', '')}；建议 {row.get('建议', '')}"
        )
        if len(rows) >= limit:
            break
    return rows


def find_report_outputs(project_dir: Path, output_dir: Path) -> tuple[Path | None, Path | None]:
    reports_dir = output_dir / "reports"
    single_html = reports_dir / f"{project_dir.name}_关节活动度.html"
    single_excel = reports_dir / f"{project_dir.name}_关节活动度.xlsx"
    if single_html.exists():
        return single_html, single_excel if single_excel.exists() else None
    index_html = output_dir / "index.html"
    if index_html.exists():
        excel_files = sorted(output_dir.rglob("*.xlsx"))
        return index_html, excel_files[0] if excel_files else None
    html_files = sorted(output_dir.rglob("*.html"))
    excel_files = sorted(output_dir.rglob("*.xlsx"))
    return (html_files[0] if html_files else None, excel_files[0] if excel_files else None)


def generate_reports_for_project(project_dir: Path, output_dir: Path) -> tuple[Path, Path]:
    assert_under_workspace(project_dir)
    assert_under_workspace(output_dir)
    export_pose2sim_outputs(project_dir, output_dir)
    root_mots = sorted((project_dir / "kinematics").glob("*.mot"))
    if root_mots:
        return generate_reports(project_dir, output_dir)

    child_dirs = [
        child
        for child in sorted(project_dir.iterdir())
        if child.is_dir() and sorted((child / "kinematics").glob("*.mot"))
    ]
    if not child_dirs:
        raise FileNotFoundError(f"未找到可生成中文报告的 .mot 文件: {project_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)
    index_rows: list[str] = []
    first_excel: Path | None = None
    for child in child_dirs:
        html_path, excel_path = generate_reports(child, output_dir / child.name)
        if first_excel is None:
            first_excel = excel_path
        rel_html = html_path.relative_to(output_dir).as_posix()
        rel_excel = excel_path.relative_to(output_dir).as_posix()
        index_rows.append(
            "<tr>"
            f"<td>{html.escape(child.name)}</td>"
            f"<td><a href='{html.escape(rel_html)}'>HTML 报告</a></td>"
            f"<td><a href='{html.escape(rel_excel)}'>Excel 报告</a></td>"
            "</tr>"
        )

    index_path = output_dir / "index.html"
    index_path.write_text(
        f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(project_dir.name)} 批处理报告入口</title>
  <style>
    body {{ font-family: "Microsoft YaHei", Arial, sans-serif; margin: 32px; color: #1f2933; }}
    table {{ border-collapse: collapse; width: 100%; max-width: 920px; }}
    th, td {{ border-bottom: 1px solid #e5e7eb; padding: 10px; text-align: left; }}
    th {{ background: #eef2f7; }}
  </style>
</head>
<body>
  <h1>{html.escape(project_dir.name)} 批处理报告入口</h1>
  <p>以下 Trial 根据可解析的 .mot 文件分别生成。</p>
  <table>
    <thead><tr><th>Trial</th><th>HTML</th><th>Excel</th></tr></thead>
    <tbody>{''.join(index_rows)}</tbody>
  </table>
</body>
</html>
""",
        encoding="utf-8",
    )
    return index_path, first_excel if first_excel is not None else index_path
