# Pose2Sim 中文自动化流水线

双击 `launch_pose2sim_gui.bat` 启动中文图形界面。该工具面向体能教练、康复师和非编程用户，帮助完成多机位视频导入、校准、同步、Pose2Sim 运行、HTML 交互报告和 Excel 关节活动度输出。

## 数据目录

- `projects/`：用户项目、原始视频、校准视频、Pose2Sim 中间结果。
- `outputs/`：最终报告和 Pose2Sim 结果副本。

这些目录默认不会上传到 GitHub。

## 环境

默认使用：

`D:\Application\Anaconda\envs\sports3d\python.exe`

该环境需要能导入 Pose2Sim、OpenSim、customtkinter、plotly、openpyxl，并可调用 ffmpeg。

详细操作见 [中文使用说明](docs/中文使用说明.md)。
