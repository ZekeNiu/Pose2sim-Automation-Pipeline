from __future__ import annotations

import html
import json
import re
import shutil
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


def _parse_quality_diagnostics(project_dir: Path) -> QualityDiagnostic:
    sections: dict[str, list[str]] = {
        "校准": [],
        "同步": [],
        "三维重建": [],
        "逆运动学": [],
        "缺失/插值": [],
        "解释建议": [],
    }
    rows: list[dict[str, str | float]] = []
    risk_scores: list[int] = []
    log_path = project_dir / "logs.txt"
    if log_path.exists():
        text = log_path.read_text(encoding="utf-8", errors="replace")
        residual_matches = re.findall(r"Residual \(RMS\) calibration errors.*", text, flags=re.IGNORECASE)
        if residual_matches:
            values = _numbers_from_brackets(residual_matches[-1])
            if values:
                max_value = max(values)
                mean_value = sum(values) / len(values)
                score = 1 if max_value <= 1 else 2 if max_value <= 3 else 3
                risk_scores.append(score)
                msg = f"每台相机校准 RMS 约为 {', '.join(f'{v:.3g}' for v in values)}，平均 {mean_value:.3g}，最大 {max_value:.3g}。"
                sections["校准"].append(msg + (" 该数值较低，校准质量较好。" if score == 1 else " 该数值偏高时，应检查棋盘格/场景点是否清晰、分布是否充分。"))
                rows.append({"类别": "校准", "指标": "校准 RMS", "数值": ", ".join(f"{v:.3g}" for v in values), "解释": sections["校准"][-1]})

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
                risk_scores.append(score)
                msg = f"同步相关系数范围 {min(correlations):.2f}-{max(correlations):.2f}，帧偏移约为 {', '.join(offsets) if offsets else '未解析'} 帧。"
                sections["同步"].append(msg + (" 同步可信度较高。" if score == 1 else " 相关性一般时，小幅相位差可能影响快速动作峰值。"))
                rows.append({"类别": "同步", "指标": "相关系数/帧偏移", "数值": msg, "解释": sections["同步"][-1]})

        reprojection_summary = re.findall(
            r"Mean reprojection error for all points.*? is ([0-9.]+) px.*?(?:corresponds to|~) ([0-9.]+) m",
            text,
            flags=re.IGNORECASE,
        )
        if reprojection_summary:
            px, meters = [float(value) for value in reprojection_summary[-1]]
            score = 1 if px <= 8 else 2 if px <= 15 else 3
            risk_scores.append(score)
            msg = f"所有点平均重投影误差约 {px:.2f} px，粗略对应 {meters:.3f} m。"
            sections["三维重建"].append(msg + (" 三维重建误差处于可用范围。" if score <= 2 else " 误差偏高，建议优先检查相机标定、遮挡和关键点识别。"))
            rows.append({"类别": "三维重建", "指标": "平均重投影误差", "数值": f"{px:.2f} px / {meters:.3f} m", "解释": sections["三维重建"][-1]})
        excluded_matches = re.findall(r"In average, ([0-9.]+) cameras had to be excluded", text, flags=re.IGNORECASE)
        if excluded_matches:
            excluded = float(excluded_matches[-1])
            score = 1 if excluded <= 0.2 else 2 if excluded <= 0.8 else 3
            risk_scores.append(score)
            msg = f"为满足误差阈值，平均每帧约排除 {excluded:.2f} 台相机。"
            sections["三维重建"].append(msg + (" 说明多机位一致性较好。" if score == 1 else " 排除相机较多时，部分关节可能依赖较少视角。"))
            rows.append({"类别": "三维重建", "指标": "排除相机比例", "数值": f"{excluded:.2f}", "解释": sections["三维重建"][-1]})

    ik_files = sorted((project_dir / "kinematics").glob("*marker_errors*.sto"))
    if not ik_files:
        ik_files = sorted((project_dir / "kinematics").glob("_ik_marker_errors.sto"))
    for ik_file in ik_files:
        table = _read_sto_table(ik_file)
        if not table.empty and "marker_error_RMS" in table:
            mean_rms = float(table["marker_error_RMS"].mean())
            max_err = float(table.get("marker_error_max", pd.Series(dtype=float)).max())
            score = 1 if mean_rms <= 0.02 else 2 if mean_rms <= 0.04 else 3
            risk_scores.append(score)
            msg = f"IK marker RMS 平均 {mean_rms:.4f} m，最大 marker error {max_err:.4f} m。"
            sections["逆运动学"].append(msg + (" 模型拟合较稳定。" if score == 1 else " 该误差提示关节角应优先看趋势和较大变化。"))
            rows.append({"类别": "逆运动学", "指标": "IK marker error", "数值": f"RMS {mean_rms:.4f} m / max {max_err:.4f} m", "解释": sections["逆运动学"][-1]})

    trc_files = sorted((project_dir / "pose-3d").glob("*.trc"))
    for trc_file in trc_files[:3]:
        text = trc_file.read_text(encoding="utf-8", errors="replace")
        nan_count = text.lower().count("nan")
        if nan_count:
            risk_scores.append(2)
            msg = f"{trc_file.name} 中发现 {nan_count} 个 NaN 文本。"
            sections["缺失/插值"].append(msg + " 如果集中出现在某些时段，相关关节角峰值需要谨慎解释。")
            rows.append({"类别": "缺失/插值", "指标": "NaN", "数值": str(nan_count), "解释": sections["缺失/插值"][-1]})

    confidence = _score_label(risk_scores)
    if confidence == "高":
        summary = "综合置信度：高。当前可解析指标整体较稳定，适合查看关节活动度趋势和主要峰值。"
    elif confidence == "中":
        summary = "综合置信度：中。结果可用于动作趋势分析，但小幅差异和快速峰值需要结合视频与完整诊断谨慎解释。"
    elif confidence == "低":
        summary = "综合置信度：低。建议优先检查校准、同步、遮挡和关键点识别后再解释关节角。"
    else:
        summary = "综合置信度：未知。未解析到足够质量指标，请同时查看 Pose2Sim 原始日志、叠加视频和 OpenSim 输出。"

    sections["解释建议"].append("本报告只解释数据质量和关节活动度趋势，不构成医学诊断或康复处方。")
    if not rows:
        rows.append({"类别": "诊断", "指标": "未解析", "数值": "未知", "解释": summary})
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


def _copy_report_videos(project_dir: Path, media_dir: Path) -> list[ReportVideo]:
    media_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[ReportVideo] = []
    for video in _select_report_video_sources(project_dir):
        target = media_dir / video.media_name
        shutil.copy2(video.source, target)
        outputs.append(video)
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
    if len(mot_files) > 1:
        selector_html = (
            "<label for='subject-select'>人员/结果：</label>"
            f"<select id='subject-select'>{''.join(selector_options)}</select>"
        )
    video_grid = _video_grid(videos)
    html_path = reports_dir / f"{project_dir.name}_关节活动度.html"
    html_path.write_text(
        f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(project_dir.name)} 关节活动度报告</title>
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
    <h1>{html.escape(project_dir.name)} 关节活动度报告</h1>
    <div>角度来源：OpenSim 逆运动学 .mot 文件；单位：度。</div>
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
    <section class="panel">{selector_html or '当前报告包含 1 个可解析 .mot 文件。'}</section>
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
    cards = "\n".join(
        "<div class='video-card'>"
        f"<h3>{html.escape(video.label)} <span class='notice'>({html.escape(video.source_type)})</span></h3>"
        f"<video class='sync-video' controls preload='metadata' src='media/{html.escape(video.media_name)}'></video>"
        "</div>"
        for video in videos
    )
    return f"<div class='video-grid {count_class}'>{cards}</div>"


def _diagnostic_sections_html(sections: dict[str, list[str]]) -> str:
    blocks: list[str] = []
    for title, lines in sections.items():
        if not lines:
            continue
        items = "".join(f"<li>{html.escape(line)}</li>" for line in lines)
        blocks.append(f"<section><h4>{html.escape(title)}</h4><ul>{items}</ul></section>")
    return "".join(blocks) or "<p>未发现可解析的完整诊断信息。</p>"


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
