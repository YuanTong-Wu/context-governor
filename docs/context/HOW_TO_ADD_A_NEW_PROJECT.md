# 如何添加新项目

添加项目时不要复制 `BOOT.md` 形成新入口树。项目只需要注册表记录、项目目录和预算。

```bash
python3 tools/context/project/init_project_context.py \
  --root <workspace> \
  --project-id my_project \
  --project-name "My Project" \
  --project-root <project-root>
```

如需设为主动项目，追加：

```bash
--activate
```

随后运行：

```bash
tools/context/run_context_governor_all.sh --root <workspace>
```

新项目必须有自己的 `CONTEXT_BUDGET.json`，并且启动包仍受全局预算约束。
