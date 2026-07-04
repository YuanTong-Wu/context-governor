# 多项目 Context Control

Context governor 的职责是让每次启动只读取小而确定的上下文，同时保留对完整项目资料的可查询访问。

## 核心文件

- `BOOT.md`：短入口，只放路由、预算、指针。
- `context/global/PROJECT_REGISTRY.json`：项目注册表。
- `context/global/ACTIVE_PROJECT.json`：当前主动项目。
- `context/projects/<project_id>/CONTEXT_BUDGET.json`：项目预算。
- `context/generated/startup_bundles/<project_id>_STARTUP_BUNDLE.md`：启动包。
- `context/indexes/views/*_VIEW.csv`：启动安全索引视图。

## 规则

- 启动不读取全量索引。
- 全量索引只能通过 `tools/context/query_index.py` 查询。
- 大文件、raw evidence、holdout 路径必须经过 `tools/context/read_gate/read_context_file.py`。
- 每次 context 控制层改动后运行 `tools/context/run_context_governor_all.sh`。
