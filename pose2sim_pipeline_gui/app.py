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
from .runner import PipelineRunner
from .workspace import ProjectWorkspace, list_projects

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")


class Pose2SimChineseApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        ensure_workspace()
        self.title("Pose2Sim 中文自动化流水线")
        self.geometry("1280x820")
        self.minsize(1100, 720)
        self.log_queue: queue.Queue[str] = queue.Queue()
        self.workspace: ProjectWorkspace | None = None
        self.runner = PipelineRunner(SPORTS3D_PYTHON)
        self._build_ui()
        self.after(150, self._drain_log_queue)

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.tabs = ctk.CTkTabview(self)
        self.tabs.grid(row=0, column=0, sticky="nsew", padx=14, pady=14)
        for name in ["环境", "项目", "视频", "校准", "参数", "运行"]:
            self.tabs.add(name)
            self.tabs.tab(name).grid_columnconfigure(0, weight=1)
        self._build_environment_tab()
        self._build_project_tab()
        self._build_video_tab()
        self._build_calibration_tab()
        self._build_parameters_tab()
        self._build_run_tab()

    def _title(self, parent: ctk.CTkFrame, text: str, row: int) -> None:
        label = ctk.CTkLabel(parent, text=text, font=ctk.CTkFont(size=22, weight="bold"))
        label.grid(row=row, column=0, sticky="w", padx=18, pady=(18, 8))

    def _info(self, parent: ctk.CTkFrame, text: str, row: int) -> None:
        label = ctk.CTkLabel(parent, text=text, justify="left", anchor="w", wraplength=980)
        label.grid(row=row, column=0, sticky="ew", padx=18, pady=(0, 10))

    def _build_environment_tab(self) -> None:
        tab = self.tabs.tab("环境")
        self._title(tab, "1. 环境检查", 0)
        self._info(tab, "检查 Pose2Sim、OpenSim、ffmpeg 和报告依赖。首次运行或更新后建议先检查。", 1)
        buttons = ctk.CTkFrame(tab, fg_color="transparent")
        buttons.grid(row=2, column=0, sticky="ew", padx=18, pady=8)
        ctk.CTkButton(buttons, text="检查环境", command=self.check_environment).pack(side="left", padx=(0, 8))
        ctk.CTkButton(buttons, text="一键更新 Pose2Sim", command=self.update_pose2sim).pack(side="left")
        self.environment_text = ctk.CTkTextbox(tab, height=480)
        self.environment_text.grid(row=3, column=0, sticky="nsew", padx=18, pady=12)
        tab.grid_rowconfigure(3, weight=1)

    def _build_project_tab(self) -> None:
        tab = self.tabs.tab("项目")
        self._title(tab, "2. 创建或打开项目", 0)
        self._info(tab, "每个项目对应一次测试或一次采集任务。所有输入、中间结果和输出都保存在当前工作区。", 1)
        row = ctk.CTkFrame(tab, fg_color="transparent")
        row.grid(row=2, column=0, sticky="ew", padx=18, pady=8)
        ctk.CTkLabel(row, text="项目名称").pack(side="left", padx=(0, 8))
        self.project_name_entry = ctk.CTkEntry(row, width=300, placeholder_text="例如 20260620_squat")
        self.project_name_entry.pack(side="left", padx=(0, 8))
        ctk.CTkButton(row, text="创建/打开", command=self.create_or_open_project).pack(side="left", padx=(0, 8))
        ctk.CTkButton(row, text="刷新项目列表", command=self.refresh_projects).pack(side="left")
        self.project_list = ctk.CTkComboBox(tab, values=list_projects(), command=self.select_project)
        self.project_list.grid(row=3, column=0, sticky="ew", padx=18, pady=8)
        self.project_status = ctk.CTkTextbox(tab, height=380)
        self.project_status.grid(row=4, column=0, sticky="nsew", padx=18, pady=12)
        tab.grid_rowconfigure(4, weight=1)

    def _build_video_tab(self) -> None:
        tab = self.tabs.tab("视频")
        self._title(tab, "3. 导入测试视频", 0)
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
        tab.grid_rowconfigure(3, weight=1)

    def _build_calibration_tab(self) -> None:
        tab = self.tabs.tab("校准")
        self._title(tab, "4. 校准资料", 0)
        self._info(
            tab,
            "内参：每台相机拍摄移动棋盘格。外参：默认用场景点；如果不方便测量场景点，可改为棋盘格外参并把棋盘格放在地面/场景中让每台相机可见。",
            1,
        )
        controls = ctk.CTkFrame(tab, fg_color="transparent")
        controls.grid(row=2, column=0, sticky="ew", padx=18, pady=8)
        self.calibration_mode = ctk.CTkComboBox(controls, values=["scene", "board"], width=180)
        self.calibration_mode.set("scene")
        self.calibration_mode.pack(side="left", padx=(0, 8))
        ctk.CTkButton(controls, text="生成棋盘格 PDF/PNG", command=self.make_checkerboard).pack(side="left", padx=(0, 8))
        ctk.CTkButton(controls, text="导入内参棋盘格视频", command=self.import_intrinsics).pack(side="left", padx=(0, 8))
        ctk.CTkButton(controls, text="导入外参视频/图片", command=self.import_extrinsics).pack(side="left")
        self.calibration_text = ctk.CTkTextbox(tab, height=430)
        self.calibration_text.grid(row=3, column=0, sticky="nsew", padx=18, pady=12)
        self.calibration_text.insert(
            "end",
            "外参场景点格式示例，可在“参数”页修改：\n"
            + str(DEFAULT_SCENE_POINTS)
            + "\n\n场景点单位为米，点应尽量分散在运动空间内。\n",
        )
        tab.grid_rowconfigure(3, weight=1)

    def _build_parameters_tab(self) -> None:
        tab = self.tabs.tab("参数")
        self._title(tab, "5. 参数", 0)
        self._info(tab, "普通用户只需要填写身高、体重、同步时间和是否使用标记点增强；其他参数保留默认。", 1)
        grid = ctk.CTkFrame(tab, fg_color="transparent")
        grid.grid(row=2, column=0, sticky="ew", padx=18, pady=8)
        for i in range(4):
            grid.grid_columnconfigure(i, weight=1)

        self.height_entry = self._entry(grid, "身高(m，可空)", "1.75", 0, 0)
        self.mass_entry = self._entry(grid, "体重(kg)", "70", 0, 1)
        self.frame_start_entry = self._entry(grid, "开始帧(可空)", "", 0, 2)
        self.frame_end_entry = self._entry(grid, "结束帧(可空)", "", 0, 3)
        self.square_entry = self._entry(grid, "棋盘格方格(mm)", "35", 2, 0)
        self.sync_times_entry = self._entry(grid, "同步动作时间(秒，用逗号分隔)", "", 2, 1, colspan=2)

        self.speed_box = ctk.CTkComboBox(grid, values=["balanced", "fast", "accurate"])
        ctk.CTkLabel(grid, text="速度/精度").grid(row=4, column=0, sticky="w", pady=(14, 2))
        self.speed_box.grid(row=5, column=0, sticky="ew", padx=(0, 10))
        self.speed_box.set("balanced")
        self.marker_aug_var = ctk.BooleanVar(value=True)
        self.simple_model_var = ctk.BooleanVar(value=False)
        self.skip_sync_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(grid, text="使用标记点增强", variable=self.marker_aug_var).grid(row=5, column=1, sticky="w")
        ctk.CTkCheckBox(grid, text="使用快速简化 OpenSim 模型", variable=self.simple_model_var).grid(row=5, column=2, sticky="w")
        ctk.CTkCheckBox(grid, text="视频已硬同步，跳过同步", variable=self.skip_sync_var).grid(row=5, column=3, sticky="w")

        ctk.CTkLabel(tab, text="外参场景点 [[X,Y,Z], ...]，单位米").grid(row=3, column=0, sticky="w", padx=18, pady=(18, 4))
        self.scene_points_text = ctk.CTkTextbox(tab, height=220)
        self.scene_points_text.grid(row=4, column=0, sticky="nsew", padx=18, pady=(0, 12))
        self.scene_points_text.insert("end", str(DEFAULT_SCENE_POINTS))
        tab.grid_rowconfigure(4, weight=1)

    def _entry(
        self,
        parent: ctk.CTkFrame,
        label: str,
        placeholder: str,
        row: int,
        column: int,
        colspan: int = 1,
    ) -> ctk.CTkEntry:
        ctk.CTkLabel(parent, text=label).grid(row=row, column=column, columnspan=colspan, sticky="w", pady=(0, 2))
        entry = ctk.CTkEntry(parent, placeholder_text=placeholder)
        entry.grid(row=row + 1, column=column, columnspan=colspan, sticky="ew", padx=(0, 10), pady=(0, 10))
        if placeholder:
            entry.insert(0, placeholder)
        return entry

    def _build_run_tab(self) -> None:
        tab = self.tabs.tab("运行")
        self._title(tab, "6. 运行与输出", 0)
        buttons = ctk.CTkFrame(tab, fg_color="transparent")
        buttons.grid(row=1, column=0, sticky="ew", padx=18, pady=8)
        ctk.CTkButton(buttons, text="保存 Config.toml", command=self.save_config).pack(side="left", padx=(0, 8))
        ctk.CTkButton(buttons, text="运行完整流程", command=self.run_pipeline).pack(side="left", padx=(0, 8))
        ctk.CTkButton(buttons, text="仅生成报告", command=self.generate_reports).pack(side="left", padx=(0, 8))
        ctk.CTkButton(buttons, text="打开输出目录", command=self.open_output_dir).pack(side="left")
        self.run_text = ctk.CTkTextbox(tab)
        self.run_text.grid(row=2, column=0, sticky="nsew", padx=18, pady=12)
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
        height = self._optional_float(self.height_entry.get())
        mass = self._optional_float(self.mass_entry.get()) or 70.0
        frame_start = self._optional_int(self.frame_start_entry.get())
        frame_end = self._optional_int(self.frame_end_entry.get())
        square = self._optional_float(self.square_entry.get()) or 35.0
        sync_times = [float(v.strip()) for v in self.sync_times_entry.get().split(",") if v.strip()]
        return PipelineSettings(
            project_name=workspace.name,
            participant_height_m=height,
            participant_mass_kg=mass,
            frame_start=frame_start,
            frame_end=frame_end,
            speed_preset=self.speed_box.get(),
            calibration_mode=self.calibration_mode.get(),
            intrinsics_square_size_mm=square,
            extrinsics_square_size_mm=square,
            scene_points_text=self.scene_points_text.get("1.0", "end"),
            skip_synchronization=self.skip_sync_var.get(),
            sync_times_seconds=sync_times,
            marker_augmentation=self.marker_aug_var.get(),
            use_simple_model=self.simple_model_var.get(),
        )

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

    def _append(self, widget: ctk.CTkTextbox, text: str) -> None:
        widget.insert("end", text + "\n")
        widget.see("end")

    def _log(self, text: str) -> None:
        self.log_queue.put(text)

    def _drain_log_queue(self) -> None:
        while not self.log_queue.empty():
            line = self.log_queue.get()
            self._append(self.run_text, line)
        self.after(150, self._drain_log_queue)

    def _thread(self, target, start_message: str) -> None:
        self._append(self.run_text, start_message)
        thread = threading.Thread(target=target, daemon=True)
        thread.start()

    def check_environment(self) -> None:
        status = check_environment()
        self.environment_text.delete("1.0", "end")
        self.environment_text.insert("end", "\n".join(status.to_chinese_lines()))

    def update_pose2sim(self) -> None:
        def task() -> None:
            process = update_pose2sim()
            assert process.stdout is not None
            for line in process.stdout:
                self._log(line.rstrip())
            self._log(f"Pose2Sim 更新命令结束，退出码 {process.wait()}。")

        self._thread(task, "开始更新 Pose2Sim...")

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
            self.project_status.delete("1.0", "end")
            self.project_status.insert(
                "end",
                f"当前项目：{self.workspace.name}\n项目目录：{self.workspace.project_dir}\n输出目录：{self.workspace.output_dir}\n",
            )
            self.refresh_projects()
        except Exception as exc:
            messagebox.showerror("项目错误", str(exc))

    def import_trial_videos(self) -> None:
        files = [Path(p) for p in filedialog.askopenfilenames(title="选择测试视频")]
        if not files:
            return

        def task() -> None:
            try:
                workspace = self._current_workspace()
                infos = workspace.import_trial_videos(files)
                self.video_text.delete("1.0", "end")
                for info in infos:
                    self.video_text.insert(
                        "end",
                        f"{info.path.name}: {info.width}x{info.height}, fps={info.fps}, 原始旋转={info.rotation}°\n",
                    )
                self._log("测试视频导入完成。")
            except Exception as exc:
                self._log(f"测试视频导入失败: {exc}")

        self._thread(task, "开始导入测试视频...")

    def import_intrinsics(self) -> None:
        files = [Path(p) for p in filedialog.askopenfilenames(title="选择每台相机的内参棋盘格视频")]
        if not files:
            return

        def task() -> None:
            try:
                outputs = self._current_workspace().import_intrinsics(files)
                self._log("内参棋盘格视频导入完成:")
                for path in outputs:
                    self._log(str(path))
            except Exception as exc:
                self._log(f"内参导入失败: {exc}")

        self._thread(task, "开始导入内参棋盘格视频...")

    def import_extrinsics(self) -> None:
        files = [Path(p) for p in filedialog.askopenfilenames(title="选择每台相机的外参视频或图片")]
        if not files:
            return

        def task() -> None:
            try:
                outputs = self._current_workspace().import_extrinsics(files)
                self._log("外参视频/图片导入完成:")
                for path in outputs:
                    self._log(str(path))
            except Exception as exc:
                self._log(f"外参导入失败: {exc}")

        self._thread(task, "开始导入外参资料...")

    def make_checkerboard(self) -> None:
        try:
            square = self._optional_float(self.square_entry.get()) or 35.0
            png, pdf = generate_checkerboard(square_size_mm=square)
            messagebox.showinfo("棋盘格已生成", f"PNG: {png}\nPDF: {pdf}")
            os.startfile(pdf)
        except Exception as exc:
            messagebox.showerror("棋盘格错误", str(exc))

    def save_config(self) -> None:
        try:
            workspace = self._current_workspace()
            config = workspace.write_config(self._settings())
            self._append(self.run_text, f"已保存配置：{config}")
        except Exception as exc:
            messagebox.showerror("配置错误", str(exc))

    def run_pipeline(self) -> None:
        try:
            workspace = self._current_workspace()
            settings = self._settings()
            workspace.write_config(settings)
        except Exception as exc:
            messagebox.showerror("运行前检查失败", str(exc))
            return

        def task() -> None:
            code = self.runner.run_all(workspace.project_dir, settings.skip_synchronization, self._log)
            self._log(f"完整流程结束，退出码 {code}。")

        self._thread(task, "开始运行完整 Pose2Sim 流程...")

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

