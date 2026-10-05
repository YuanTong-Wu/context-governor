# 如何启动项目

启动项目只做三件事：激活项目、生成小视图、生成启动包，并对这个项目跑启动预算。

```bash
tools/context/start_project.sh default --root <workspace>
tools/context/start_project.sh my_project --root <workspace>   # 已注册的其他项目
```

输出会给出：

- 主动项目 ID。
- 启动包路径。
- 当前 runner。
- 下一步动作。

不要在启动阶段打开全量索引、长报告、case body、raw evidence 或 holdout 文件。

## 继续执行

```bash
tools/context/continue_project.sh <project_id> --root <workspace>
```

它运行项目的业务 runner。业务 runner 用 `tools/context/project/set_project_runner.py` 设置，见 `HOW_TO_ADD_A_NEW_PROJECT.md`。没有设置时，当前 runner 是治理脚本，`continue` 只提示设置方法并以退出码 3 结束，不会递归执行治理脚本。
