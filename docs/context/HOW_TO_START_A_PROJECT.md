# 如何启动项目

启动项目只做三件事：激活项目、生成小视图、生成启动包。

```bash
tools/context/start_project.sh default --root <workspace>
```

输出会给出：

- 主动项目 ID。
- 启动包路径。
- 当前 runner。
- 下一步动作。

不要在启动阶段打开全量索引、长报告、case body、raw evidence 或 holdout 文件。
