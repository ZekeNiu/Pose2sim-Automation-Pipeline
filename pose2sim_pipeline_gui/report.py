from __future__ import annotations

import html
import json
import re
import shutil
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

from .joint_metadata import metadata_for, ordered_columns
from .mot import angle_columns, read_mot
from .paths import assert_under_workspace


def _read_sto_table(path: Path) -> pd.DataFrame:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    try:
        end_idx = next(i for i, line in enumerate(lines) if line.strip().lower() == "endheader")
    except StopIteration:
        return pd.DataFrame()
    columns = lines[end_idx + 1].split()
    return pd.read_csv(path, sep=r"\s+", skiprows=end_idx + 2, names=columns, engine="python")


def _diagnostics(project_dir: Path) -> tuple[str, list[str], pd.DataFrame]:
    lines: list[str] = []
    rows: list[dict[str, str | float]] = []
    log_path = project_dir / "logs.txt"
    if log_path.exists():
        text = log_path.read_text(encoding="utf-8", errors="replace")
        for pattern, label in [
            (r"Residual.*", "校准残差"),
            (r".*offset.*correlation.*", "同步"),
            (r".*reprojection.*", "重投影"),
            (r".*warning.*", "警告"),
        ]:
            for match in re.findall(pattern, text, flags=re.IGNORECASE):
                line = re.sub(r"\s+", " ", match).strip()
                if line and len(line) < 400:
                    lines.append(f"{label}: {line}")
                    rows.append({"类别": label, "内容": line})

    ik_files = sorted((project_dir / "kinematics").glob("*marker_errors*.sto"))
    if not ik_files:
        ik_files = sorted((project_dir / "kinematics").glob("_ik_marker_errors.sto"))
    for ik_file in ik_files:
        table = _read_sto_table(ik_file)
        if not table.empty and "marker_error_RMS" in table:
            mean_rms = float(table["marker_error_RMS"].mean())
            max_err = float(table.get("marker_error_max", pd.Series(dtype=float)).max())
            msg = f"IK marker RMS 平均 {mean_rms:.4f} m，最大 marker error {max_err:.4f} m。"
            lines.append(msg)
            rows.append({"类别": "IK", "内容": msg})

    trc_files = sorted((project_dir / "pose-3d").glob("*.trc"))
    for trc_file in trc_files[:3]:
        text = trc_file.read_text(encoding="utf-8", errors="replace")
        nan_count = text.lower().count("nan")
        if nan_count:
            msg = f"{trc_file.name} 中发现 {nan_count} 个 NaN 文本，逆运动学可能受到影响。"
            lines.append(msg)
            rows.append({"类别": "缺失值", "内容": msg})

    if not lines:
        lines.append("未发现可解析的质量诊断信息。请同时查看 Pose2Sim 原始日志和图像/视频输出。")
        rows.append({"类别": "诊断", "内容": lines[0]})

    summary = lines[0]
    if len(lines) > 1:
        summary += f" 另有 {len(lines) - 1} 条完整诊断。"
    return summary, lines, pd.DataFrame(rows)


def _copy_report_videos(project_dir: Path, media_dir: Path) -> list[Path]:
    media_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    for video in sorted((project_dir / "videos").glob("*.mp4")):
        target = media_dir / video.name
        shutil.copy2(video, target)
        outputs.append(target)
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
    summary, diagnostic_lines, diagnostics_df = _diagnostics(project_dir)
    definitions_payload: dict[str, dict[str, str]] = {}
    subject_blocks: list[str] = []
    selector_options: list[str] = []
    first_excel_path = reports_dir / f"{project_dir.name}_关节活动度.xlsx"

    with pd.ExcelWriter(first_excel_path, engine="openpyxl") as writer:
        for index, mot_path in enumerate(mot_files, start=1):
            mot = read_mot(mot_path)
            columns = ordered_columns(angle_columns(mot.frame))
            if not columns:
                raise ValueError(f".mot 文件中没有可报告的关节角度列: {mot.path}")

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
        <div class="layout">
          <div class="panel">{chart_html}</div>
          <div class="panel">
            <h3>同步视频</h3>
            <div class="videos">{_video_tags(videos) or '<p>未找到可嵌入视频。</p>'}</div>
          </div>
        </div>
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

        diagnostics_df.to_excel(writer, sheet_name="质量诊断", index=False)

    full_diag_html = "<br>".join(html.escape(line) for line in diagnostic_lines)
    selector_html = ""
    if len(mot_files) > 1:
        selector_html = (
            "<label for='subject-select'>人员/结果：</label>"
            f"<select id='subject-select'>{''.join(selector_options)}</select>"
        )
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
    .summary {{ background: white; border-left: 5px solid #2563eb; padding: 16px; border-radius: 6px; }}
    .layout {{ display: grid; grid-template-columns: minmax(0, 1.6fr) minmax(320px, 0.8fr); gap: 18px; align-items: start; }}
    .panel {{ background: white; border: 1px solid #dde3ea; border-radius: 8px; padding: 16px; }}
    .videos {{ display: grid; gap: 12px; }}
    video {{ width: 100%; background: #111827; border-radius: 6px; }}
    table {{ width: 100%; border-collapse: collapse; background: white; }}
    th, td {{ border-bottom: 1px solid #e5e7eb; padding: 10px; text-align: left; font-size: 14px; }}
    th {{ background: #eef2f7; }}
    .info {{ border: 1px solid #93a4b8; border-radius: 50%; width: 20px; height: 20px; cursor: pointer; background: white; color: #2563eb; }}
    .subject-block[hidden] {{ display: none; }}
    dialog {{ border: none; border-radius: 8px; max-width: 760px; padding: 24px; box-shadow: 0 20px 60px rgba(0,0,0,.25); }}
    button.primary {{ background: #2563eb; color: white; border: none; border-radius: 6px; padding: 8px 12px; cursor: pointer; }}
    @media (max-width: 980px) {{ .layout {{ grid-template-columns: 1fr; }} main {{ padding: 16px; }} }}
  </style>
</head>
<body>
  <header>
    <h1>{html.escape(project_dir.name)} 关节活动度报告</h1>
    <div>角度来源：OpenSim 逆运动学 .mot 文件；单位：度。</div>
  </header>
  <main>
    <section class="summary">
      <strong>质量诊断与解释边界：</strong>{html.escape(summary)}
      <button class="primary" id="open-diagnostics">查看完整诊断</button>
    </section>
    <section class="panel">{selector_html or '当前报告包含 1 个可解析 .mot 文件。'}</section>
    {''.join(subject_blocks)}
  </main>
  <dialog id="info-dialog"><h3 id="info-title"></h3><div id="info-body"></div><button class="primary" onclick="this.closest('dialog').close()">关闭</button></dialog>
  <dialog id="diagnostic-dialog"><h3>完整诊断</h3><p>{full_diag_html}</p><button class="primary" onclick="this.closest('dialog').close()">关闭</button></dialog>
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
    document.querySelectorAll('[id^="joint-chart-"]').forEach(chart => {{
      const block = chart.closest('.subject-block');
      chart.on('plotly_hover', (event) => {{
        const t = event.points && event.points.length ? Number(event.points[0].x) : null;
        if (Number.isFinite(t)) {{
          block.querySelectorAll('.sync-video').forEach(v => {{
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


def _video_tags(videos: list[Path]) -> str:
    return "\n".join(
        f"<video class='sync-video' controls preload='metadata' src='media/{html.escape(video.name)}'></video>"
        for video in videos
    )


def generate_reports_for_project(project_dir: Path, output_dir: Path) -> tuple[Path, Path]:
    assert_under_workspace(project_dir)
    assert_under_workspace(output_dir)
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
  <p>以下 Trial 根据可解析的 .mot 文件分别生成。GUI 没有按项目名称做特殊处理。</p>
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
