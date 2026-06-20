from __future__ import annotations

import os
import queue
import threading
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from .checkerboard import generate_checkerboard
from .config_builder import DEFAULT_SCENE_POINTS
from .environment import check_environment, update_pose2sim
from .models import PipelineSettings
from .paths import OUTPUTS_DIR, SPORTS3D_PYTHON, ensure_workspace
from .project_state import ProjectStatus
from .runner import PipelineRunner
from .workspace import ProjectWorkspace, list_projects

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")


STEP_TABS = ["环境", "项目", "校准", "视频", "参数", "运行"]

CALIBRATION_MODE_OPTIONS = {
    "外参：场景点（推荐，精度更稳）": "scene",
    "外参：棋盘格（更简单，要求所有相机清楚看到大棋盘格）": "board",
}
CALIBRATION_MODE_LABELS = {value: label for label, value in CALIBRATION_MODE_OPTIONS.items()}

POSE_MODEL_OPTIONS = {
    "身体+足部（推荐）": "Body_with_feet",
    "全身+手腕（更慢，适合上肢细节）": "Whole_body_wrist",
    "全身（更慢，信息最多）": "Whole_body",
    "身体17点（最快，足部信息少）": "Body",
}

SPEED_PRESET_OPTIONS = {
    "平衡（balanced，默认）": "balanced",
    "更快（lightweight，适合预览）": "fast",
    "更准（performance，较慢）": "accurate",
}

BOARD_POSITION_OPTIONS = {
    "水平放置（地面/地垫）": "horizontal",
    "垂直放置（墙面/支架）": "vertical",
}


class Pose2SimChineseApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        ensure_workspace()
        self.title("Pose2Sim 中文自动化流水线")
        self.geometry("1280x820")
        self.minsize(1100, 720)
        self.log_queue: queue.Queue[tuple[str, str]] = queue.Queue()
        self.workspace: ProjectWorkspace | None = None
        self.project_status_info: ProjectStatus | None = None
        self.runner = PipelineRunner(SPORTS3D_PYTHON)
        self.update_button: ctk.CTkButton | None = None
        self._build_ui()
        self.after(150, self._drain_log_queue)

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.tabs = ctk.CTkTabview(self)
        self.tabs.grid(row=0, column=0, sticky="nsew", padx=14, pady=14)
        for name in STEP_TABS:
            self.tabs.add(name)
            self.tabs.tab(name).grid_columnconfigure(0, weight=1)
        self._build_environment_tab()
        self._build_project_tab()
        self._build_calibration_tab()
        self._build_video_tab()
        self._build_parameters_tab()
        self._build_run_tab()

    def _title(self, parent: ctk.CTkFrame, text: str, row: int) -> None:
        label = ctk.CTkLabel(parent, text=text, font=ctk.CTkFont(size=22, weight="bold"))
        label.grid(row=row, column=0, sticky="w", padx=18, pady=(18, 8))

    def _info(self, parent: ctk.CTkFrame, text: str, row: int, wraplength: int = 980) -> None:
        label = ctk.CTkLabel(parent, text=text, justify="left", anchor="w", wraplength=wraplength)
        label.grid(row=row, column=0, sticky="ew", padx=18, pady=(0, 10))

    def _info_button(self, parent: ctk.CTkFrame, title: str, body: str) -> ctk.CTkButton:
        return ctk.CTkButton(
            parent,
            text="i",
            width=26,
            height=26,
            corner_radius=13,
            command=lambda: messagebox.showinfo(title, body),
        )

    def _label_with_info(
        self,
        parent: ctk.CTkFrame,
        text: str,
        row: int,
        column: int,
        info_title: str,
        info_body: str,
        columnspan: int = 1,
    ) -> None:
        holder = ctk.CTkFrame(parent, fg_color="transparent")
        holder.grid(row=row, column=column, columnspan=columnspan, sticky="w", pady=(0, 2))
        ctk.CTkLabel(holder, text=text).pack(side="left")
        self._info_button(holder, info_title, info_body).pack(side="left", padx=(6, 0))

    def _entry(
        self,
        parent: ctk.CTkFrame,
        label: str,
        default: str,
        row: int,
        column: int,
        colspan: int = 1,
        info_title: str | None = None,
        info_body: str | None = None,
    ) -> ctk.CTkEntry:
        if info_title and info_body:
            self._label_with_info(parent, label, row, column, info_title, info_body, colspan)
        else:
            ctk.CTkLabel(parent, text=label).grid(
                row=row, column=column, columnspan=colspan, sticky="w", pady=(0, 2)
            )
        entry = ctk.CTkEntry(parent, placeholder_text=default)
        entry.grid(row=row + 1, column=column, columnspan=colspan, sticky="ew", padx=(0, 10), pady=(0, 10))
        if default:
            entry.insert(0, default)
        return entry

    def _checkbox_with_info(
        self,
        parent: ctk.CTkFrame,
        text: str,
        variable: ctk.BooleanVar,
        row: int,
        column: int,
        info_title: str,
        info_body: str,
        colspan: int = 1,
    ) -> None:
        holder = ctk.CTkFrame(parent, fg_color="transparent")
        holder.grid(row=row, column=column, columnspan=colspan, sticky="w", padx=(0, 10), pady=(6, 10))
        ctk.CTkCheckBox(holder, text=text, variable=variable).pack(side="left")
        self._info_button(holder, info_title, info_body).pack(side="left", padx=(8, 0))

    def _step_nav(self, parent: ctk.CTkFrame, current: str, row: int) -> None:
        nav = ctk.CTkFrame(parent, fg_color="transparent")
        nav.grid(row=row, column=0, sticky="ew", padx=18, pady=(10, 18))
        index = STEP_TABS.index(current)
        if index > 0:
            previous_step = STEP_TABS[index - 1]
            ctk.CTkButton(
                nav,
                text=f"上一步：{previous_step}",
                fg_color="#64748b",
                command=lambda: self._go_step(previous_step),
            ).pack(side="left", padx=(0, 8))
        if index < len(STEP_TABS) - 1:
            next_step = STEP_TABS[index + 1]
            ctk.CTkButton(
                nav,
                text=f"下一步：{next_step}",
                command=lambda: self._go_next(current, next_step),
            ).pack(side="right")

    def _go_step(self, target: str) -> None:
        self.tabs.set(target)

    def _go_next(self, current: str, target: str) -> None:
        if current == "项目" and not self.project_name_entry.get().strip():
            messagebox.showwarning("需要项目名称", "请先创建或打开一个项目。项目会保存视频、校准资料、配置和输出报告。")
            return
        if current in {"校准", "视频", "参数"} and self.workspace is None and not self.project_name_entry.get().strip():
            messagebox.showwarning("需要项目", "建议先在“项目”页创建项目，再继续后续步骤。")
        self.tabs.set(target)

    def _build_environment_tab(self) -> None:
        tab = self.tabs.tab("环境")
        self._title(tab, "1. 环境检查", 0)
        self._info(tab, "检查 Pose2Sim、OpenSim、ffmpeg 和报告依赖。首次运行、更新 Pose2Sim 后，建议先执行一次检查。", 1)
        buttons = ctk.CTkFrame(tab, fg_color="transparent")
        buttons.grid(row=2, column=0, sticky="ew", padx=18, pady=8)
        ctk.CTkButton(buttons, text="检查环境", command=self.check_environment).pack(side="left", padx=(0, 8))
        self.update_button = ctk.CTkButton(buttons, text="一键更新 Pose2Sim", command=self.update_pose2sim)
        self.update_button.pack(side="left")
        self.environment_text = ctk.CTkTextbox(tab, height=480)
        self.environment_text.grid(row=3, column=0, sticky="nsew", padx=18, pady=12)
        self._step_nav(tab, "环境", 4)
        tab.grid_rowconfigure(3, weight=1)

    def _build_project_tab(self) -> None:
        tab = self.tabs.tab("项目")
        self._title(tab, "2. 创建或打开项目", 0)
        self._info(tab, "每个项目对应一次采集任务。所有输入、中间结果和输出都保存在当前工作区，不写入 Anaconda 环境目录。", 1)
        row = ctk.CTkFrame(tab, fg_color="transparent")
        row.grid(row=2, column=0, sticky="ew", padx=18, pady=8)
        ctk.CTkLabel(row, text="项目名称").pack(side="left", padx=(0, 8))
        self.project_name_entry = ctk.CTkEntry(row, width=300, placeholder_text="例如 20260620_squat")
        self.project_name_entry.pack(side="left", padx=(0, 8))
        ctk.CTkButton(row, text="创建/打开", command=self.create_or_open_project).pack(side="left", padx=(0, 8))
        ctk.CTkButton(row, text="刷新项目列表", command=self.refresh_projects).pack(side="left")
        object_row = ctk.CTkFrame(tab, fg_color="transparent")
        object_row.grid(row=3, column=0, sticky="ew", padx=18, pady=8)
        ctk.CTkLabel(object_row, text="分析对象").pack(side="left", padx=(0, 8))
        self.analysis_object_var = ctk.StringVar(value="单人")
        ctk.CTkSegmentedButton(
            object_row,
            values=["单人", "多人"],
            variable=self.analysis_object_var,
            command=self._on_analysis_object_change,
        ).pack(side="left", padx=(0, 10))
        self.multi_person_hint = ctk.CTkLabel(
            object_row,
            text="默认单人、单次动作、多机位。多人属于高级用法，对遮挡、同步和人员匹配要求更高。",
            anchor="w",
            justify="left",
            wraplength=760,
        )
        self.multi_person_hint.pack(side="left", fill="x", expand=True)
        self.project_list = ctk.CTkComboBox(tab, values=list_projects(), command=self.select_project)
        self.project_list.grid(row=4, column=0, sticky="ew", padx=18, pady=8)
        self.project_status = ctk.CTkTextbox(tab, height=380)
        self.project_status.grid(row=5, column=0, sticky="nsew", padx=18, pady=12)
        self._step_nav(tab, "项目", 6)
        tab.grid_rowconfigure(5, weight=1)

    def _build_calibration_tab(self) -> None:
        tab = self.tabs.tab("校准")
        tab.grid_rowconfigure(0, weight=1)
        content = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        content.grid(row=0, column=0, sticky="nsew")
        content.grid_columnconfigure(0, weight=1)

        self._title(content, "3. 校准资料", 0)
        self._info(
            content,
            "先完成校准准备，再录制或导入正式动作视频。内参用于描述镜头畸变；外参用于描述每台相机在空间中的位置和朝向。相机一旦移动，外参需要重做。",
            1,
        )

        mode_row = ctk.CTkFrame(content, fg_color="transparent")
        mode_row.grid(row=2, column=0, sticky="ew", padx=18, pady=8)
        ctk.CTkLabel(mode_row, text="外参方法").pack(side="left", padx=(0, 8))
        self._info_button(
            mode_row,
            "外参方法怎么选",
            "推荐优先选择“场景点”：用真实空间中可测量的点建立坐标系，通常比小棋盘格更适合全身动作。\n\n"
            "如果没有条件测量场景点，可以选择“棋盘格”：操作更简单，但棋盘格必须足够大，并且所有相机都能清楚看到。",
        ).pack(side="left", padx=(0, 10))
        self.calibration_mode = ctk.CTkComboBox(
            mode_row,
            values=list(CALIBRATION_MODE_OPTIONS.keys()),
            width=420,
            command=self._on_calibration_mode_change,
        )
        self.calibration_mode.set(CALIBRATION_MODE_LABELS["scene"])
        self.calibration_mode.pack(side="left", padx=(0, 8))

        board_grid = ctk.CTkFrame(content, fg_color="transparent")
        board_grid.grid(row=3, column=0, sticky="ew", padx=18, pady=8)
        for i in range(4):
            board_grid.grid_columnconfigure(i, weight=1)
        self.intrinsics_square_entry = self._entry(
            board_grid,
            "内参棋盘格方格边长(mm)",
            "35",
            0,
            0,
            info_title="内参棋盘格尺寸",
            info_body="内参用于描述每台相机镜头畸变。默认生成 A4、4 x 7 内角点、35 mm 方格。\n\n"
            "打印时选择“实际大小/100%”，不要选择“适应页面”。打印后量一个方格；如果不是 35 mm，请把实测边长填在这里。",
        )
        self.extrinsics_square_entry = self._entry(
            board_grid,
            "外参棋盘格方格边长(mm)",
            "45",
            0,
            1,
            info_title="外参棋盘格尺寸",
            info_body="只有选择“棋盘格外参”时需要。默认建议 A3、4 x 7 内角点、45 mm 方格，是打印便利和全身外参稳定性的折中。\n\n"
            "如果只能用 A4，也可以尝试，但全身动作优先推荐“场景点外参”。",
        )
        self.board_position_frame = ctk.CTkFrame(board_grid, fg_color="transparent")
        self.board_position_frame.grid(row=0, column=2, rowspan=2, sticky="ew", padx=(0, 10))
        self.board_position_frame.grid_columnconfigure(0, weight=1)
        self._label_with_info(
            self.board_position_frame,
            "棋盘格放置方式",
            0,
            0,
            "棋盘格外参放置方式",
            "只有选择“棋盘格外参”时需要。水平放置表示棋盘格在地面或地垫上；垂直放置表示棋盘格固定在墙面、架子或竖直平面上。\n\n"
            "这个选项必须和实际录制方式一致，否则外参坐标系方向会错。",
        )
        self.board_position_box = ctk.CTkComboBox(self.board_position_frame, values=list(BOARD_POSITION_OPTIONS.keys()))
        self.board_position_box.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        self.board_position_box.set("水平放置（地面/地垫）")
        ctk.CTkLabel(
            board_grid,
            text="内参通常 A4 就够；棋盘格外参建议 A3 或更大。两种棋盘格可以规格不同，GUI 会分别写入 Config。",
            anchor="w",
            justify="left",
            wraplength=360,
        ).grid(row=1, column=3, sticky="w", pady=(0, 10))

        buttons = ctk.CTkFrame(content, fg_color="transparent")
        buttons.grid(row=4, column=0, sticky="ew", padx=18, pady=8)
        ctk.CTkButton(buttons, text="生成内参棋盘格 A4", command=self.make_intrinsics_checkerboard).pack(side="left", padx=(0, 8))
        ctk.CTkButton(buttons, text="生成外参棋盘格 A3", command=self.make_extrinsics_checkerboard).pack(side="left", padx=(0, 8))
        ctk.CTkButton(buttons, text="导入内参棋盘格视频", command=self.import_intrinsics).pack(side="left", padx=(0, 8))
        ctk.CTkButton(buttons, text="导入外参视频/图片", command=self.import_extrinsics).pack(side="left")

        guide_text = ctk.CTkTextbox(content, height=230)
        guide_text.grid(row=5, column=0, sticky="ew", padx=18, pady=12)
        guide_text.insert(
            "end",
            "内参视频怎么录：\n"
            "1. 每台相机单独录一段棋盘格视频，保持正式拍摄时的分辨率、焦距、变焦、横竖屏方向和对焦方式。\n"
            "2. 每段约 20-40 秒。拿着棋盘格缓慢移动，让棋盘格出现在画面中央、四角、近处、远处，并有轻微倾斜和旋转。\n"
            "3. 多数画面里棋盘格要完整可见，避免反光、运动模糊、遮挡和严重过曝。\n\n"
            "场景点外参怎么做：\n"
            "1. 先定义坐标系，例如运动区域地面中心为 P1=[0,0,0]，前方是 X 正方向，左方是 Y 正方向，上方是 Z 正方向，单位是米。\n"
            "2. 3D 坐标来自现场测量：卷尺、激光测距仪、地砖尺寸、场地标线或已知物体尺寸都可以。它不是视频里的像素坐标。\n"
            "3. 点上建议放彩色胶带十字、编号贴纸、小锥桶、反光点；如果墙角、箱体角点、跑台边缘足够清楚，也可以不额外放东西。\n"
            "4. 正式摆好所有相机后，不要再移动相机。拍每个机位都能看到这些点的外参资料：清晰图片即可，录 3-5 秒静态视频也可以。\n"
            "5. 外参资料拍完后，只要相机不动，点位标记可以移走，再录正式动作视频。后续在 GUI/校准工具里点选时，点击顺序必须和表格 P1、P2、P3 一致。\n\n"
            "棋盘格外参怎么做：\n"
            "1. 相机固定后，把较大的外参棋盘格放在所有相机都能清楚看到的位置，可水平放在地面，也可垂直固定。\n"
            "2. 建议使用 GUI 生成的 A3/45 mm 外参棋盘格；A4 可用但不推荐全身动作。录制 3-5 秒清晰视频或导入清晰图片。\n"
            "3. 内参棋盘格和外参棋盘格参数是独立的；如果实际打印尺寸不同，请分别修改上方两个方格边长。\n",
        )
        guide_text.configure(state="disabled")

        self.scene_points_frame = ctk.CTkFrame(content, fg_color="transparent")
        self.scene_points_frame.grid(row=6, column=0, sticky="ew", padx=18, pady=(2, 8))
        for col in range(5):
            self.scene_points_frame.grid_columnconfigure(col, weight=1 if col else 0)
        self._label_with_info(
            self.scene_points_frame,
            "外参场景点表格（单位：米）",
            0,
            0,
            "场景点怎么填写",
            "这里填写真实世界中的 3D 坐标，不是视频里的像素坐标。\n\n"
            "示例：地面中心可以设为 P1=[0,0,0]，向前 1 米是 [1,0,0]，向左 0.3 米是 [0,0.3,0]。点越分散、越容易在各机位中准确点击，外参越可靠。",
            columnspan=5,
        )
        headers = ["点编号", "X", "Y", "Z", "现场说明"]
        for col, header in enumerate(headers):
            ctk.CTkLabel(self.scene_points_frame, text=header).grid(row=1, column=col, sticky="w", pady=(4, 2))
        self.scene_point_entries: list[tuple[ctk.CTkEntry, ctk.CTkEntry, ctk.CTkEntry, ctk.CTkEntry, ctk.CTkEntry]] = []
        default_notes = [
            "地面左前角/胶带十字",
            "地面前中点/胶带十字",
            "前方低高度点",
            "地面右前角/胶带十字",
            "地面左中点/胶带十字",
            "原点/地面中心",
            "中心低高度点",
            "地面右中点/胶带十字",
            "地面左后角/胶带十字",
            "地面右后角/胶带十字",
        ]
        for row_index, coords in enumerate(DEFAULT_SCENE_POINTS[:10], start=2):
            point_entry = ctk.CTkEntry(self.scene_points_frame, width=70)
            point_entry.insert(0, f"P{row_index - 1}")
            x_entry = ctk.CTkEntry(self.scene_points_frame)
            y_entry = ctk.CTkEntry(self.scene_points_frame)
            z_entry = ctk.CTkEntry(self.scene_points_frame)
            note_entry = ctk.CTkEntry(self.scene_points_frame)
            for entry, value, col in [
                (point_entry, f"P{row_index - 1}", 0),
                (x_entry, str(coords[0]), 1),
                (y_entry, str(coords[1]), 2),
                (z_entry, str(coords[2]), 3),
                (note_entry, default_notes[row_index - 2], 4),
            ]:
                if entry is not point_entry:
                    entry.insert(0, value)
                entry.grid(row=row_index, column=col, sticky="ew", padx=(0, 8), pady=2)
            self.scene_point_entries.append((point_entry, x_entry, y_entry, z_entry, note_entry))

        self.calibration_text = ctk.CTkTextbox(content, height=100)
        self.calibration_text.grid(row=7, column=0, sticky="ew", padx=18, pady=(6, 12))
        self.calibration_text.insert("end", "校准资料导入状态会显示在这里。\n")
        self._step_nav(content, "校准", 8)
        self._on_calibration_mode_change()

    def _build_video_tab(self) -> None:
        tab = self.tabs.tab("视频")
        self._title(tab, "4. 导入测试视频", 0)
        self._info(
            tab,
            "建议至少 2 个机位：一个正面，一个 45° 侧前方；相机高度约在髋部，主体全程可见，背景尽量简洁。导入后会自动修正手机旋转并转成浏览器兼容 MP4。",
            1,
        )
        ctk.CTkButton(tab, text="选择每个机位的测试视频", command=self.import_trial_videos).grid(
            row=2, column=0, sticky="w", padx=18, pady=8
        )
        self.video_text = ctk.CTkTextbox(tab, height=470)
        self.video_text.grid(row=3, column=0, sticky="nsew", padx=18, pady=12)
        self._step_nav(tab, "视频", 4)
        tab.grid_rowconfigure(3, weight=1)

    def _build_parameters_tab(self) -> None:
        tab = self.tabs.tab("参数")
        tab.grid_rowconfigure(0, weight=1)
        content = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        content.grid(row=0, column=0, sticky="nsew")
        content.grid_columnconfigure(0, weight=1)

        self._title(content, "5. 参数", 0)
        self._info(
            content,
            "基础区只放普通用户需要经常设置的内容。高级区会影响稳定性，不确定时保持默认。",
            1,
        )
        grid = ctk.CTkFrame(content, fg_color="transparent")
        grid.grid(row=2, column=0, sticky="ew", padx=18, pady=8)
        for i in range(4):
            grid.grid_columnconfigure(i, weight=1)

        self.height_entry = self._entry(
            grid,
            "身高(m；多人可逗号分隔)",
            "1.75",
            0,
            0,
            info_title="身高",
            info_body="身高用于 OpenSim 缩放和标记点增强。单人填写一个值；多人可按人员顺序填写多个值，例如 1.75,1.68。\n\n"
            "留空时 Pose2Sim 会尝试自动估计，但标记点增强和尺度可能更不稳定。",
        )
        self.mass_entry = self._entry(
            grid,
            "体重(kg；多人可逗号分隔)",
            "70",
            0,
            1,
            info_title="体重",
            info_body="体重主要影响后续动力学分析，对本工具输出的关节角度影响很小。单人填写一个值；多人可按人员顺序填写多个值。未知时可以保留 70 kg。",
        )
        self.frame_start_entry = self._entry(
            grid,
            "开始帧(可空)",
            "",
            0,
            2,
            info_title="分析开始帧",
            info_body="只想分析视频中间某一段时填写。留空表示由 Pose2Sim 使用完整视频或自动范围。",
        )
        self.frame_end_entry = self._entry(
            grid,
            "结束帧(可空)",
            "",
            0,
            3,
            info_title="分析结束帧",
            info_body="结束帧必须大于开始帧。普通用户通常留空，先跑完整视频更稳。",
        )
        self.sync_times_entry = self._entry(
            grid,
            "同步动作大致时间(秒，逗号分隔)",
            "",
            2,
            0,
            colspan=2,
            info_title="同步动作大致时间",
            info_body="手机通常不能硬件同步。这里填每个机位中同步动作大致发生的秒数，例如 1.2, 1.4。\n\n"
            "不需要精确到帧；Pose2Sim 会在附近搜索最大速度/相关峰。只要大致时间落在搜索范围内，通常可以工作。",
        )

        self._label_with_info(
            grid,
            "姿态模型",
            2,
            2,
            "姿态模型",
            "默认“身体+足部”适合下肢、步态、深蹲和大多数体能动作。\n\n"
            "全身模型会尝试识别更多点，但更慢，也更容易受遮挡影响；只有确实需要上肢/手部细节时再改。",
        )
        self.pose_model_box = ctk.CTkComboBox(grid, values=list(POSE_MODEL_OPTIONS.keys()))
        self.pose_model_box.grid(row=3, column=2, sticky="ew", padx=(0, 10), pady=(0, 10))
        self.pose_model_box.set("身体+足部（推荐）")

        self._label_with_info(
            grid,
            "模型模式",
            2,
            3,
            "模型模式",
            "更快：速度优先，适合预览。\n平衡：默认推荐。\n更准：更慢，但通常更适合最终分析。\n\n"
            "界面中的中文选项会写入 Pose2Sim 官方的 lightweight / balanced / performance 模式。",
        )
        self.speed_box = ctk.CTkComboBox(grid, values=list(SPEED_PRESET_OPTIONS.keys()))
        self.speed_box.grid(row=3, column=3, sticky="ew", padx=(0, 10), pady=(0, 10))
        self.speed_box.set("平衡（balanced，默认）")

        self.marker_aug_var = ctk.BooleanVar(value=True)
        self.save_overlay_var = ctk.BooleanVar(value=True)
        self.skip_sync_var = ctk.BooleanVar(value=False)
        self._checkbox_with_info(
            grid,
            "使用标记点增强",
            self.marker_aug_var,
            4,
            0,
            "标记点增强",
            "默认开启。它会基于 Pose2Sim 的增强模型生成更适合 OpenSim 的标记点。\n\n"
            "如果模型文件或结果条件不满足，后续运行会自动跳过并记录原因。",
        )
        self._checkbox_with_info(
            grid,
            "保存叠加检测视频",
            self.save_overlay_var,
            4,
            1,
            "叠加检测视频",
            "默认保存。它会把识别到的人体关键点叠加到视频上，方便检查遮挡、错人、左右混淆和低质量帧。\n\n"
            "关闭后速度和空间占用会更好，但质控资料更少。",
        )
        self._checkbox_with_info(
            grid,
            "视频已硬同步，跳过同步",
            self.skip_sync_var,
            4,
            2,
            "跳过同步",
            "只有在多台相机已经通过硬件或同一设备严格同步时才勾选。\n\n"
            "普通手机多机位通常不要勾选，应录制明显同步动作并填写大致时间。",
            colspan=2,
        )

        advanced_header = ctk.CTkFrame(content, fg_color="transparent")
        advanced_header.grid(row=3, column=0, sticky="ew", padx=18, pady=(14, 4))
        self.advanced_button = ctk.CTkButton(
            advanced_header,
            text="展开高级参数",
            fg_color="#64748b",
            command=self._toggle_advanced_parameters,
        )
        self.advanced_button.pack(side="left")
        ctk.CTkButton(
            advanced_header,
            text="恢复高级默认值",
            fg_color="#64748b",
            command=self._reset_advanced_defaults,
        ).pack(side="left", padx=(8, 0))

        self.advanced_frame = ctk.CTkFrame(content, fg_color="#f8fafc")
        self.advanced_frame.grid(row=4, column=0, sticky="ew", padx=18, pady=(0, 10))
        for i in range(4):
            self.advanced_frame.grid_columnconfigure(i, weight=1)
        ctk.CTkLabel(
            self.advanced_frame,
            text="高级参数会改变 Pose2Sim 的稳定性和结果解释边界。不确定时保持默认。",
            anchor="w",
            justify="left",
            wraplength=980,
        ).grid(row=0, column=0, columnspan=4, sticky="ew", padx=12, pady=(12, 8))
        self.sync_range_entry = self._entry(
            self.advanced_frame,
            "同步搜索范围(秒)",
            "2",
            1,
            0,
            info_title="同步搜索范围",
            info_body="Pose2Sim 会在“大致时间”前后这个范围内寻找同步事件。大致时间不够准时可以增大到 3-4 秒；范围太大可能匹配到错误动作。",
        )
        self.filter_entry = self._entry(
            self.advanced_frame,
            "滤波截止频率(Hz)",
            "6",
            1,
            1,
            info_title="滤波截止频率",
            info_body="用于平滑三维点轨迹。过低会抹掉快速动作，过高会保留噪声。普通体能动作通常保持 6 Hz。",
        )
        self.feet_floor_var = ctk.BooleanVar(value=False)
        self.symmetry_var = ctk.BooleanVar(value=True)
        self.simple_model_var = ctk.BooleanVar(value=False)
        self._checkbox_with_info(
            self.advanced_frame,
            "启用足部贴地修正",
            self.feet_floor_var,
            3,
            0,
            "足部贴地修正",
            "尝试把足部标记点调整到更合理的地面关系。适合站立、步态等地面接触明显的动作；跳跃腾空或非地面动作不建议开启。",
        )
        self._checkbox_with_info(
            self.advanced_frame,
            "启用左右对称",
            self.symmetry_var,
            3,
            1,
            "左右对称",
            "OpenSim 缩放时假设左右肢段尺寸对称。大多数普通分析保持开启；如果受试者明显不对称或有特殊假肢/支具，才考虑关闭。",
        )
        self._checkbox_with_info(
            self.advanced_frame,
            "使用快速简化 OpenSim 模型",
            self.simple_model_var,
            3,
            2,
            "简化 OpenSim 模型",
            "可以降低运行复杂度，但模型细节更少。首次分析建议关闭，只有运行失败或需要快速预览时再尝试。",
            colspan=2,
        )
        self.advanced_frame.grid_remove()
        self._step_nav(content, "参数", 5)

    def _build_run_tab(self) -> None:
        tab = self.tabs.tab("运行")
        self._title(tab, "6. 运行与输出", 0)
        buttons = ctk.CTkFrame(tab, fg_color="transparent")
        buttons.grid(row=1, column=0, sticky="ew", padx=18, pady=8)
        ctk.CTkButton(buttons, text="保存 Config.toml", command=self.save_config).pack(side="left", padx=(0, 8))
        ctk.CTkButton(buttons, text="保存配置并运行完整流程", command=self.run_pipeline).pack(side="left", padx=(0, 8))
        ctk.CTkButton(buttons, text="按现有 Config 运行", command=self.run_existing_config).pack(side="left", padx=(0, 8))
        ctk.CTkButton(buttons, text="从缺失阶段继续", command=self.run_missing_steps).pack(side="left", padx=(0, 8))
        ctk.CTkButton(buttons, text="仅生成报告", command=self.generate_reports).pack(side="left", padx=(0, 8))
        ctk.CTkButton(buttons, text="打开输出目录", command=self.open_output_dir).pack(side="left")
        self.run_text = ctk.CTkTextbox(tab)
        self.run_text.grid(row=2, column=0, sticky="nsew", padx=18, pady=12)
        self._step_nav(tab, "运行", 3)
        tab.grid_rowconfigure(2, weight=1)

    def _current_workspace(self) -> ProjectWorkspace:
        if self.workspace is None:
            name = self.project_name_entry.get().strip()
            if not name:
                raise ValueError("请先创建或打开项目。")
            self.workspace = ProjectWorkspace(name)
            self.workspace.create()
        return self.workspace

    def _settings(self) -> PipelineSettings:
        workspace = self._current_workspace()
        multi_person = self.analysis_object_var.get() == "多人"
        heights = self._float_list(self.height_entry.get())
        masses = self._float_list(self.mass_entry.get())
        height = heights[0] if heights else None
        mass = masses[0] if masses else 70.0
        frame_start = self._optional_int(self.frame_start_entry.get())
        frame_end = self._optional_int(self.frame_end_entry.get())
        intrinsics_square = self._optional_float(self.intrinsics_square_entry.get()) or 35.0
        extrinsics_square = self._optional_float(self.extrinsics_square_entry.get()) or 45.0
        sync_times = [float(v.strip()) for v in self.sync_times_entry.get().split(",") if v.strip()]
        calibration_mode = self._calibration_mode_value()
        scene_points = self._scene_points_table_text() if calibration_mode == "scene" else ""
        return PipelineSettings(
            project_name=workspace.name,
            multi_person=multi_person,
            participant_height_m=height,
            participant_heights_m=heights if multi_person else [],
            participant_mass_kg=mass,
            participant_masses_kg=masses if multi_person else [],
            frame_start=frame_start,
            frame_end=frame_end,
            pose_model=self._pose_model_value(),
            speed_preset=self._speed_preset_value(),
            calibration_mode=calibration_mode,
            intrinsics_square_size_mm=intrinsics_square,
            intrinsics_extension=workspace.calibration_extension("intrinsics"),
            extrinsics_square_size_mm=extrinsics_square,
            extrinsics_extension=workspace.calibration_extension("extrinsics"),
            extrinsics_board_position=self._board_position_value(),
            scene_points_text=scene_points,
            skip_synchronization=self.skip_sync_var.get(),
            sync_times_seconds=sync_times,
            sync_search_range_seconds=self._optional_float(self.sync_range_entry.get()) or 2.0,
            marker_augmentation=self.marker_aug_var.get(),
            use_simple_model=self.simple_model_var.get(),
            save_overlay_video=self.save_overlay_var.get(),
            feet_on_floor=self.feet_floor_var.get(),
            right_left_symmetry=self.symmetry_var.get(),
            filter_cutoff_hz=self._optional_float(self.filter_entry.get()) or 6.0,
        )

    def _calibration_mode_value(self) -> str:
        return CALIBRATION_MODE_OPTIONS.get(self.calibration_mode.get(), self.calibration_mode.get())

    def _pose_model_value(self) -> str:
        return POSE_MODEL_OPTIONS.get(self.pose_model_box.get(), self.pose_model_box.get())

    def _speed_preset_value(self) -> str:
        return SPEED_PRESET_OPTIONS.get(self.speed_box.get(), self.speed_box.get())

    def _board_position_value(self) -> str:
        return BOARD_POSITION_OPTIONS.get(self.board_position_box.get(), self.board_position_box.get())

    @staticmethod
    def _optional_float(value: str) -> float | None:
        value = value.strip()
        if not value:
            return None
        return float(value)

    @staticmethod
    def _optional_int(value: str) -> int | None:
        value = value.strip()
        if not value:
            return None
        return int(value)

    @staticmethod
    def _float_list(value: str) -> list[float]:
        parts = [part.strip() for part in value.replace("，", ",").split(",") if part.strip()]
        return [float(part) for part in parts]

    def _scene_points_table_text(self) -> str:
        lines = ["点编号,X,Y,Z,现场说明"]
        for point_entry, x_entry, y_entry, z_entry, note_entry in self.scene_point_entries:
            point = point_entry.get().strip()
            x = x_entry.get().strip()
            y = y_entry.get().strip()
            z = z_entry.get().strip()
            note = note_entry.get().strip()
            if not point and not x and not y and not z:
                continue
            if not point or not x or not y or not z:
                raise ValueError("场景点表格中每一行都需要点编号、X、Y、Z；不用的行请全部留空。")
            lines.append(f"{point},{x},{y},{z},{note}")
        return "\n".join(lines)

    def _append(self, widget: ctk.CTkTextbox, text: str) -> None:
        widget.insert("end", text + "\n")
        widget.see("end")

    def _replace_text(self, widget: ctk.CTkTextbox, text: str) -> None:
        widget.delete("1.0", "end")
        widget.insert("end", text)
        widget.see("end")

    def _queue_log(self, target: str, text: str) -> None:
        self.log_queue.put((target, text))

    def _log(self, text: str) -> None:
        self._queue_log("run", text)

    def _drain_log_queue(self) -> None:
        while not self.log_queue.empty():
            target, line = self.log_queue.get()
            widget = {
                "run": getattr(self, "run_text", None),
                "environment": getattr(self, "environment_text", None),
                "calibration": getattr(self, "calibration_text", None),
                "video": getattr(self, "video_text", None),
            }.get(target)
            if widget is not None:
                self._append(widget, line)
        self.after(150, self._drain_log_queue)

    def _thread(self, target, start_message: str, log_target: str = "run") -> None:
        self._queue_log(log_target, start_message)
        thread = threading.Thread(target=target, daemon=True)
        thread.start()

    def _on_calibration_mode_change(self, _choice: str | None = None) -> None:
        if not hasattr(self, "scene_points_frame"):
            return
        if self._calibration_mode_value() == "scene":
            self.scene_points_frame.grid()
            self.board_position_frame.grid_remove()
        else:
            self.scene_points_frame.grid_remove()
            self.board_position_frame.grid()

    def _toggle_advanced_parameters(self) -> None:
        if self.advanced_frame.winfo_ismapped():
            self.advanced_frame.grid_remove()
            self.advanced_button.configure(text="展开高级参数")
        else:
            self.advanced_frame.grid()
            self.advanced_button.configure(text="收起高级参数")

    def _reset_advanced_defaults(self) -> None:
        self.sync_range_entry.delete(0, "end")
        self.sync_range_entry.insert(0, "2")
        self.filter_entry.delete(0, "end")
        self.filter_entry.insert(0, "6")
        self.feet_floor_var.set(False)
        self.symmetry_var.set(True)
        self.simple_model_var.set(False)
        messagebox.showinfo("已恢复默认", "高级参数已恢复为推荐默认值。")

    def check_environment(self) -> None:
        status = check_environment()
        self.environment_text.delete("1.0", "end")
        self.environment_text.insert("end", "\n".join(status.to_chinese_lines()))

    def update_pose2sim(self) -> None:
        if self.update_button is not None:
            self.update_button.configure(state="disabled", text="正在更新...")
        self.environment_text.delete("1.0", "end")
        self.environment_text.insert("end", "正在检查/更新 Pose2Sim，请稍候...\n")

        def finish(message: str, is_error: bool = False) -> None:
            if self.update_button is not None:
                self.update_button.configure(state="normal", text="一键更新 Pose2Sim")
            if is_error:
                messagebox.showerror("Pose2Sim 更新失败", message)
            else:
                messagebox.showinfo("Pose2Sim 更新完成", message)

        def task() -> None:
            try:
                process = update_pose2sim()
                assert process.stdout is not None
                for line in process.stdout:
                    self._queue_log("environment", line.rstrip())
                code = process.wait()
                self._queue_log("environment", f"Pose2Sim 更新命令结束，退出码 {code}。")
                self._queue_log("environment", "正在重新检查环境...")
                status = check_environment()
                for line in status.to_chinese_lines():
                    self._queue_log("environment", line)
                if code == 0:
                    self.after(
                        0,
                        lambda: finish("更新命令已结束，环境检查已刷新。若版本未变化，通常表示当前已经是可安装的最新版本。"),
                    )
                else:
                    self.after(0, lambda: finish(f"更新命令退出码为 {code}，请查看环境页日志。", True))
            except Exception as exc:
                message = str(exc)
                self._queue_log("environment", f"更新失败: {message}")
                self.after(0, lambda: finish(message, True))

        thread = threading.Thread(target=task, daemon=True)
        thread.start()

    def _on_analysis_object_change(self, _choice: str | None = None) -> None:
        if self.analysis_object_var.get() == "多人":
            self.multi_person_hint.configure(
                text="多人属于高级用法：建议减少遮挡、录制明显同步动作，并在身高/体重中按人员顺序用逗号填写多个值。"
            )
        else:
            self.multi_person_hint.configure(
                text="默认单人、单次动作、多机位。多人属于高级用法，对遮挡、同步和人员匹配要求更高。"
            )

    def _refresh_project_status(self) -> None:
        if self.workspace is None:
            return
        self.project_status_info = self.workspace.status()
        if self.project_status_info.multi_person:
            self.analysis_object_var.set("多人")
            self._on_analysis_object_change()
        lines = [
            f"当前项目：{self.workspace.name}",
            f"项目目录：{self.workspace.project_dir}",
            f"输出目录：{self.workspace.output_dir}",
            "",
            *self.project_status_info.summary_lines(),
            "",
            "已有 Config.toml 时，GUI 默认不会自动覆盖。需要重新生成配置时，会先备份为 Config.backup_YYYYMMDD_HHMMSS.toml。",
            "批处理项目会交给 Pose2Sim 官方层级配置读取逻辑，不会被强行转换成单项目配置。",
        ]
        self.project_status.delete("1.0", "end")
        self.project_status.insert("end", "\n".join(lines) + "\n")

    def refresh_projects(self) -> None:
        self.project_list.configure(values=list_projects())

    def select_project(self, name: str) -> None:
        if not name:
            return
        self.project_name_entry.delete(0, "end")
        self.project_name_entry.insert(0, name)
        self.create_or_open_project()

    def create_or_open_project(self) -> None:
        try:
            name = self.project_name_entry.get()
            self.workspace = ProjectWorkspace(name)
            self.workspace.create()
            self._refresh_project_status()
            self.refresh_projects()
        except Exception as exc:
            messagebox.showerror("项目错误", str(exc))

    def import_trial_videos(self) -> None:
        files = [Path(p) for p in filedialog.askopenfilenames(title="选择测试视频")]
        if not files:
            return
        try:
            workspace = self._current_workspace()
        except Exception as exc:
            messagebox.showerror("项目错误", str(exc))
            return

        def task() -> None:
            try:
                infos = workspace.import_trial_videos(files)
                lines = []
                for info in infos:
                    lines.append(f"{info.path.name}: {info.width}x{info.height}, fps={info.fps}, 原始旋转={info.rotation}°")
                self.after(0, lambda: self._replace_text(self.video_text, "\n".join(lines) + "\n"))
                self.after(0, self._refresh_project_status)
                self._queue_log("video", "测试视频导入完成。")
                self._log("测试视频导入完成。")
            except Exception as exc:
                self._queue_log("video", f"测试视频导入失败: {exc}")
                self._log(f"测试视频导入失败: {exc}")

        self._thread(task, "开始导入测试视频...", "video")

    def import_intrinsics(self) -> None:
        files = [Path(p) for p in filedialog.askopenfilenames(title="选择每台相机的内参棋盘格视频")]
        if not files:
            return
        try:
            workspace = self._current_workspace()
        except Exception as exc:
            messagebox.showerror("项目错误", str(exc))
            return

        def task() -> None:
            try:
                outputs = workspace.import_intrinsics(files)
                self._queue_log("calibration", "内参棋盘格视频导入完成:")
                for path in outputs:
                    self._queue_log("calibration", str(path))
                self.after(0, self._refresh_project_status)
                self._log("内参棋盘格视频导入完成。")
            except Exception as exc:
                self._queue_log("calibration", f"内参导入失败: {exc}")
                self._log(f"内参导入失败: {exc}")

        self._thread(task, "开始导入内参棋盘格视频...", "calibration")

    def import_extrinsics(self) -> None:
        files = [Path(p) for p in filedialog.askopenfilenames(title="选择每台相机的外参视频或图片")]
        if not files:
            return
        try:
            workspace = self._current_workspace()
        except Exception as exc:
            messagebox.showerror("项目错误", str(exc))
            return

        def task() -> None:
            try:
                outputs = workspace.import_extrinsics(files)
                self._queue_log("calibration", "外参视频/图片导入完成:")
                for path in outputs:
                    self._queue_log("calibration", str(path))
                self.after(0, self._refresh_project_status)
                self._log("外参视频/图片导入完成。")
            except Exception as exc:
                self._queue_log("calibration", f"外参导入失败: {exc}")
                self._log(f"外参导入失败: {exc}")

        self._thread(task, "开始导入外参资料...", "calibration")

    def _make_checkerboard(self, *, square_entry: ctk.CTkEntry, page_size: str, purpose: str) -> None:
        try:
            square = self._optional_float(square_entry.get()) or (35.0 if page_size == "A4" else 45.0)
            png, pdf = generate_checkerboard(square_size_mm=square, page_size=page_size, purpose=purpose)
            messagebox.showinfo(
                "棋盘格已生成",
                f"PNG: {png}\nPDF: {pdf}\n\n打印时选择“实际大小/100%”，不要选择“适应页面”。打印后请测量一个方格边长和 100 mm 检查尺。",
            )
            os.startfile(pdf)
        except Exception as exc:
            messagebox.showerror("棋盘格错误", str(exc))

    def make_intrinsics_checkerboard(self) -> None:
        self._make_checkerboard(square_entry=self.intrinsics_square_entry, page_size="A4", purpose="intrinsics")

    def make_extrinsics_checkerboard(self) -> None:
        self._make_checkerboard(square_entry=self.extrinsics_square_entry, page_size="A3", purpose="extrinsics")

    def save_config(self) -> None:
        try:
            workspace = self._current_workspace()
            config = self._write_config_with_prompt(workspace, self._settings())
            if config is not None:
                self._append(self.run_text, f"已保存配置：{config}")
                self._refresh_project_status()
        except Exception as exc:
            messagebox.showerror("配置错误", str(exc))

    def _write_config_with_prompt(self, workspace: ProjectWorkspace, settings: PipelineSettings) -> Path | None:
        try:
            return workspace.write_config(settings, overwrite=False)
        except FileExistsError as exc:
            overwrite = messagebox.askyesno(
                "保护已有配置",
                f"{exc}\n\n是否先备份已有 Config.toml，再用当前 GUI 参数覆盖？\n选择“否”会保留原配置。",
            )
            if not overwrite:
                self._append(self.run_text, "已保留现有 Config.toml，未覆盖。")
                return None
            config = workspace.write_config(settings, overwrite=True, backup=True)
            self._append(self.run_text, "已备份旧 Config.toml，并写入当前 GUI 配置。")
            return config

    def run_pipeline(self) -> None:
        try:
            workspace = self._current_workspace()
            settings = self._settings()
            config = self._write_config_with_prompt(workspace, settings)
            if config is None:
                return
            self._refresh_project_status()
        except Exception as exc:
            messagebox.showerror("运行前检查失败", str(exc))
            return

        def task() -> None:
            code = self.runner.run_all(workspace.project_dir, settings.skip_synchronization, self._log)
            self._log(f"完整流程结束，退出码 {code}。")
            self.after(0, self._refresh_project_status)

        self._thread(task, "开始运行完整 Pose2Sim 流程...")

    def run_existing_config(self) -> None:
        try:
            workspace = self._current_workspace()
            if not (workspace.project_dir / "Config.toml").exists():
                messagebox.showwarning("缺少配置", "当前项目没有 Config.toml。请先保存 GUI 配置，或打开已有 Pose2Sim 项目。")
                return
            skip_synchronization = self.skip_sync_var.get()
            self._refresh_project_status()
        except Exception as exc:
            messagebox.showerror("运行前检查失败", str(exc))
            return

        def task() -> None:
            code = self.runner.run_all(workspace.project_dir, skip_synchronization, self._log)
            self._log(f"按现有 Config 运行结束，退出码 {code}。")
            self.after(0, self._refresh_project_status)

        self._thread(task, "开始按现有 Config.toml 运行 Pose2Sim...")

    def run_missing_steps(self) -> None:
        try:
            workspace = self._current_workspace()
            if not (workspace.project_dir / "Config.toml").exists():
                messagebox.showwarning("缺少配置", "当前项目没有 Config.toml。请先保存配置，才能从缺失阶段继续。")
                return
            status = workspace.status()
            skip_synchronization = self.skip_sync_var.get()
            steps = status.missing_steps
            self._append(self.run_text, "准备运行缺失阶段：" + " → ".join(steps))
        except Exception as exc:
            messagebox.showerror("运行前检查失败", str(exc))
            return

        def task() -> None:
            code = self.runner.run_steps(workspace.project_dir, steps, skip_synchronization, self._log)
            self._log(f"缺失阶段运行结束，退出码 {code}。")
            self.after(0, self._refresh_project_status)

        self._thread(task, "开始从缺失阶段继续运行 Pose2Sim...")

    def generate_reports(self) -> None:
        try:
            workspace = self._current_workspace()
        except Exception as exc:
            messagebox.showerror("项目错误", str(exc))
            return

        def task() -> None:
            code = self.runner.generate_reports(workspace.project_dir, self._log)
            self._log(f"报告生成结束，退出码 {code}。")

        self._thread(task, "开始生成报告...")

    def open_output_dir(self) -> None:
        try:
            workspace = self._current_workspace()
            workspace.output_dir.mkdir(parents=True, exist_ok=True)
            os.startfile(workspace.output_dir)
        except Exception:
            os.startfile(OUTPUTS_DIR)


def main() -> None:
    app = Pose2SimChineseApp()
    app.mainloop()
