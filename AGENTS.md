# Repository Guidelines

## Project Structure & Module Organization
- 入口 `main.py`（PyQt5），核心 UI 在 `modules/ui_core.py`。
- 业务模块位于 `modules/`：`price_monitor.py`、`web_monitor.py`、`apatch.py`、`filter.py`、`auto_flask.py`、`notice_manager.py`、`update_checker.py`、`config.py`、`startup_profiler.py`、`lazy_boot.py`。
- 打包与发布：`main.spec`、`runtime_hook.py`；自动发布 `release.py`。
- 资源：`scripts/auto_HPES.ahk`、图标 `app.ico`；构建产物 `dist/POE2PriceAid_v*.exe`（勿提交）。
- 版本元数据：`version.txt`、`update.json`、`version_Notice.txt`、`version_过滤器.txt`、`version_A大补丁.json`。

## Build, Test, and Development Commands
- Windows 初始化：`.venv\Scripts\activate && pip install -r requirements.txt`
- 本地运行：`python main.py`
- 单文件打包：`pyinstaller --clean --noconfirm main.spec`
- 全量发布：`python release.py`（自动递增版本、更新元数据、构建并上传）
- 启动分析：设置 `POE2_PROFILE_STARTUP=1`（可选 `POE2_EXIT_AFTER_MS=3000`）

## Coding Style & Naming Conventions
- Python 3.10+，PEP 8，4 空格缩进。
- 命名：文件/模块 `lower_snake_case`；类 `PascalCase`；函数/变量 `lower_snake_case`；常量 `UPPER_SNAKE_CASE`。
- 避免阻塞 UI 线程；耗时库按需导入或用 `modules.lazy_boot` 延迟（如 `requests/bs4/lxml`）。
- UI 字符串与中文注释保持一致，禁止无意义重构与大范围重格式化。

## Testing Guidelines
- 首选 `pytest`；用例置于 `tests/`，命名 `test_*.py`。
- 冒烟检查：应用能启动、主窗体快速显示、标签页延迟加载、更新/公告操作不卡 UI。
- 网络相关用例请 Mock HTTP，避免真实外呼。

## Commit & Pull Request Guidelines
- 提交信息简洁聚焦，例如：`feat(ui): defer heavy imports at startup`、`fix(updater): handle timeout`。
- 禁止提交 `dist/`、`.venv/` 等本地产物。
- PR 需包含：目的、变更摘要、验证步骤/命令、UI 变更截图、关联 Issue；打包相关变更请同步更新 `main.spec` 并说明对 `release.py` 的影响。
- 版本需保持一致：`version.txt`、`update.json`、`modules/config.py:CURRENT_VERSION`；优先使用 `release.py` 完成版本递增。

## Agent-Specific Notes
- 仅做最小化、聚焦的差异；使用 `apply_patch` 编辑文件；遵循本指南的风格与命名。

