# Pose2Sim 中文自动化流水线

双击 `launch_pose2sim_gui.bat` 启动中文图形界面。该工具面向体能教练、康复师和非编程用户，按 `环境 → 项目 → 校准 → 视频 → 参数 → 运行` 引导完成 Pose2Sim 多机位分析、HTML 交互报告和 Excel 关节活动度输出。

## 数据目录

- `projects/`：用户项目、原始视频、校准视频、Pose2Sim 中间结果。
- `outputs/`：最终报告和 Pose2Sim 结果副本。

这些目录默认不会上传到 GitHub。

## 环境

默认使用：

`D:\Application\Anaconda\envs\sports3d\python.exe`

该环境需要能导入 Pose2Sim、OpenSim、customtkinter、plotly、openpyxl，并可调用 ffmpeg。GUI 的环境页也提供“一键更新 Pose2Sim”和可见更新日志。

详细操作见 [中文使用说明](docs/中文使用说明.md)。
