# 如何添加新项目

添加项目时不要复制 `BOOT.md` 形成新入口树。项目只需要注册表记录、项目目录和预算。

```bash
python3 tools/context/project/init_project_context.py \
  --root <workspace> \
  --project-id my_project \
  --project-name "My Project" \
  --project-root <project-root> \
  --activate
```

项目根目录可以在工作区之外。注册之后，`start_project.sh`、`continue_project.sh` 和总控只需要项目 ID；不传 `--project-root` / `--project-name` 时保留注册表里的值。

随后启动并验证这个项目：

```bash
bash tools/context/start_project.sh my_project --root <workspace>
bash tools/context/run_context_governor_all.sh --root <workspace> --project-id my_project
```

`start_project.sh` 为这个项目建索引、视图和启动包，并按这个项目自己的视图目录（`context/projects/my_project/indexes/views/`）和全量索引路径跑启动预算。总控不带 `--project-id` 时验证的是 `default`，并把当前项目切回 `default`。

新项目有自己的 `CONTEXT_BUDGET.json`，启动包仍受全局预算约束。

## 业务 runner

`continue_project.sh` 运行项目的业务 runner。没有设置时，当前 runner 是治理脚本，`continue` 拒绝执行（退出码 3）。设置：

```bash
python3 tools/context/project/set_project_runner.py --root <workspace> --project-id my_project tools/run_main.sh
bash tools/context/continue_project.sh my_project --root <workspace>
```

- runner 必须是项目根目录 `tools/` 下的 `.py` 或 `.sh` 文件（这样会被 `RUNNER_INDEX` 收录）；`tools/context`、`tools/dev`、`tools/keeper` 里的治理脚本会被拒绝。
- 设置写进注册表的 `business_runner` 字段和项目的任务状态；之后 `update_task_state.py`、`init_project_context.py` 和每次运行都保留它。
- `continue_project.sh` 在工作区根目录下调用它，并传 `--root <workspace>`。
- 取消：`set_project_runner.py --root <workspace> --project-id my_project --clear`。
