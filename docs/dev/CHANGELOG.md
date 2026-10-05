# Dev Changelog

## 2026-10-05

- 开源整理：补充 README、LICENSE、中立的示例配置和测试。
- 语义漂移规则、必需规则短语和 BOOT 规则关键词改为从 `context/SYSTEM_INVARIANTS.json` 读取（`forbidden_claims`、`required_rules`、`boot_rule_keywords`）。
- 注册表里工作区内的 `project_root` 存成相对路径。
- 全新工作区第一次运行总控时先写任务状态（`bootstrap_task_state`），不再因缺少 `TASK_STATE.json` 而阻断。
- `regression_check.py` 按当前项目找启动包；`context_budget_check.py` 支持 `--root` 和 `--config`。
- 新增示例工作区 `examples/workspace/`、`scripts/make_workspace.sh`、`scripts/run_tests.sh` 和 `tests/test_workspace.py`。
- `default` 以外的项目：启动预算改为按项目自己的视图目录和全量索引路径检查（`startup_budget_test.py --project-id`），并拦截任何已注册项目的全量索引；`start_project.sh`、`continue_project.sh` 和总控对外部项目可以通过。
- `start_project.sh` 和总控不再把已注册项目的根目录和名称重置成工作区根目录和 `Default Project`。
- 新增 `tools/context/project/set_project_runner.py`：在注册表里设置业务 runner（`business_runner`），任务状态和每次运行都保留它；`continue` 先判断治理 runner 再判断文件是否存在。
- 路径检查按项目根目录找 runner；集成测试恢复它们切换过的当前项目；Keeper 只采用同一项目的启动预算判决。

## 2026-06-24

- 建立多项目 context governor。
- 新增项目注册表、主动项目指针、启动包预算、索引小视图、读取闸门、递归入口检测。
- 新增本地 dev change-control 脚本：preflight、impact、schema、path、invariant、regression、summary。
- 新增统一验证入口 `tools/context/run_context_governor_all.sh`。
