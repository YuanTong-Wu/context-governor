# 如何修改复杂项目

复杂项目修改要先缩小读集，再执行。

## 流程

1. 运行 `tools/context/start_project.sh <project_id>`。
2. 用 `context/generated/startup_bundles/<project_id>_STARTUP_BUNDLE.md` 确认当前 runner 和下一步。
3. 用 `tools/context/query_index.py` 找到必要文件。
4. 用读取闸门打开必要片段。
5. 修改代码或配置。
6. 运行 `tools/dev/run_dev_checks.sh`。
7. 运行 `tools/context/run_context_governor_all.sh`。

## 判断完成

- `BOOT.md` 仍低于预算。
- 启动包通过预算检查。
- 递归入口检测通过。
- 项目注册表和主动项目一致。
- holdout 状态仍为 `LOCKED`。
