# 如何修改系统文件

这套仓库把启动上下文当成受控接口。修改 `BOOT.md`、`context/SYSTEM_INVARIANTS.json`、`context/TASK_STATE.json`、`context/global/*`、`tools/context/*` 前，先运行：

```bash
tools/dev/run_dev_checks.sh --root <workspace>
```

## 改动顺序

1. 先确认改动目标属于哪个面：入口、项目注册表、索引、读取闸门、schema、invariant、测试。
2. 用 `tools/dev/preflight_change.py` 看风险分级。
3. 改文件。
4. 运行 `tools/context/run_context_governor_all.sh`。
5. 查看 `var/context_governor_2026_06_24/verdict.json`。

## 禁止事项

- 不新增替代启动入口文件。
- 不把长报告、全量索引、raw evidence、holdout 内容加入启动上下文。
- 不把 generated summary 提升为高于源文件的权威来源。
- 不触碰外部副作用接口（支付、部署、账户变更）。
