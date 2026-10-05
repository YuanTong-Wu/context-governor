---
name: context-keeper
description: Use this skill when the user asks for the Chinese "上下文管家" / Context Keeper wrapper around the local Context Governor, including project status, next action, continue, change checks, entry repair, or governor reports without exposing raw context indexes.
---

# Context Keeper / 上下文管家

上下文管家是现有 Context Governor 的中文薄封装。它只负责把底层治理脚本翻译成安全、短小、可读的日常命令，不新增治理逻辑。

## 规则

- 使用 `tools/keeper/keeper.py` 作为入口。
- 面向用户的输出必须是中文。
- 不读取或打印完整 `FILE_INDEX.csv`、`GAP_INDEX.csv`、`EVIDENCE_INDEX.csv` 或原始 `gap_queue.csv`。
- 不打开 holdout，不执行外部副作用动作，不扩写 `BOOT.md`。
- 回归测试产生的 `gap_queue.csv` 历史行默认只当审计历史；只有 final verdict 或当前状态显示 active blocker 时才提醒用户。
- 如果 `current_runner` 是 governor/control runner，用“上下文系统健康，当前没有业务 runner”的话术解释，不递归执行；用户要设置业务 runner 时，用 `python3 tools/context/project/set_project_runner.py tools/<runner>.sh`。

## 命令

```bash
上下文管家
管家 现在做到哪了
管家 下一步
管家 我要改 BOOT.md
python tools/keeper/keeper.py open
python tools/keeper/keeper.py status
python tools/keeper/keeper.py next
python tools/keeper/keeper.py continue
python tools/keeper/keeper.py check-change --changed-file BOOT.md
python tools/keeper/keeper.py fix
python tools/keeper/keeper.py report
python tools/keeper/keeper.py help
```

需要 shell 包装器时使用 `tools/keeper/keeper.sh <command>`。

## Status 必须包含

1. 当前项目
2. 入口状态
3. BOOT 行数
4. 启动包状态
5. holdout 状态
6. 当前阶段
7. 最新判决
8. 当前最大 active blocker
9. 下一步建议
10. 最新报告路径
