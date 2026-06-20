# Pose2Sim 中文 GUI 实施计划

## 状态
- 当前阶段：实现首版端到端工具。
- 工作区：`D:\Application\Biomechanics\Pose2sim_Pipeline`
- 约束：不参考废弃 `Pose2sim_Automation`、`Sports2d` 旧代码；不上传用户输入/输出。

## 阶段
1. 基础工程与目录保护
   - 创建 `.gitignore`、包结构、任务记录。
   - 保护 `projects/`、`outputs/`、视频和日志。
2. 核心能力
   - 路径约束与项目目录管理。
   - `Config.toml` 自动生成。
   - 棋盘格资源生成。
   - 视频方向检测与 ffmpeg 规范化命令。
3. Pose2Sim 集成
   - 环境检查。
   - 分阶段运行官方 Pose2Sim。
   - 日志与错误解释。
4. 报告
   - 解析 `.mot` 关节角度。
   - 生成 HTML 交互报告与 Excel。
   - 质量诊断摘要与完整诊断。
5. GUI
   - CustomTkinter 中文界面。
   - BAT 启动。
6. 验证与发布
   - 单元测试、样例报告测试、GUI 导入冒烟测试。
   - 初始化 Git 仓库、提交并推送。

## 决策
- GUI 形态：BAT 启动 Python 桌面窗口。
- 首版范围：单人、多机位、手机/普通相机。
- 校准：默认内参棋盘格 + 外参场景点；同时支持内外参都用棋盘格。
- 报告角度来源：OpenSim `.mot`，不使用原始坐标。

