# Context Governor 与 Keeper

给 AI 编程 Agent 用的上下文治理工具。它让 Agent 每次启动只读一小份、可核对的上下文：一个有预算的 `BOOT.md`、一个启动包、几张有行数上限的索引视图。完整索引、原始证据和封存（holdout）材料被挡在启动上下文之外；一组审计脚本给出可回归的判决，判决不通过就阻断。Keeper（上下文管家）是它的中文命令入口。

纯 Python 标准库加 bash，不需要安装任何依赖。English summary at the end.

## 为什么需要它

长期项目里，Agent 的启动文件往往越写越长：入口文件里塞进项目历史、全量索引和原始数据；为了解释入口又新建一个“入口的入口”；生成的摘要被当成比源文件更可信的依据。结果是上下文窗口被占满、被压缩，Agent 读到的是过期或失真的信息，还很难发现。

这个工具把启动上下文当成一个受控接口：

- **有预算**：BOOT、任务状态、启动包、索引视图都有行数和字符数上限。
- **只放指针**：启动时读视图和指针，完整内容按需查询、按需读取。
- **有审计**：完整性、启动预算、递归入口都有独立的检查和判决文件。
- **可回归**：一条命令重跑全部步骤和测试，重复运行结果一致。

## 组成

| 部分 | 位置 | 作用 |
|---|---|---|
| BOOT 与任务状态 | `tools/context/build_boot_context.py`、`update_task_state.py` | 生成不超过 80 行、4000 字符的 `BOOT.md`，只放规则子集、指针和下一步；写 `context/TASK_STATE.json` |
| 完整性审计 | `tools/context/context_integrity_check.py`、`context_repair.py` | 检查 BOOT 大小与指针、递归入口文件、BOOT 里的违禁内容（全量 gap 列表、原始正文、结果表）、语义漂移、holdout 锁定、生成摘要的权威上限；可自动修复和隔离 |
| 索引与视图 | `build_{file,runner,case,evidence,gap}_index.py`、`build_index_views.py`、`query_index.py` | 全量索引只供查询；启动只读有上限的视图（默认最多 200 行、30000 字符）和分片 |
| 启动包与预算 | `build_startup_bundle.py`、`startup_budget_test.py` | 生成启动包；发现全量索引、原始证据、结果表或 holdout 内容混进启动上下文时给出阻断判决 |
| 读取闸门 | `tools/context/read_gate/` | 大文件必须给理由并限定长度；原始证据只返回指针；holdout/sealed 路径拒绝读取；每次读取都记日志 |
| 递归入口检测 | `recursive_entry_detector.py` | 按文件名和内容找出 `BOOT_FOR_BOOT`、`START_HERE_V2` 这类替代入口，白名单之外即阻断 |
| 多项目 | `project/init_project_context.py`、`start_project.sh`、`continue_project.sh` | 项目注册表、当前项目、项目级预算；`continue` 拒绝把治理脚本当成业务 runner 重跑（退出码 3） |
| 改动控制 | `tools/dev/` | 改动前分级（preflight）、影响面、schema、路径一致性、不变量、回归检查和改动摘要 |
| 总控 | `run_context_governor_all.sh`、`run_context_control_all.sh` | 每步带超时，逐步写审计 CSV；最终报告从独立的审计文件读取完整性判决，而不是从汇总判决读 |
| Keeper | `tools/keeper/`、根目录的 `管家`、`上下文管家`、`k`、`ctx` | 中文命令入口：状态、下一步、继续、改动前检查、修复、报告 |
| Markdown 预算 | `tools/context_budget_check.py` | 按角色给 Markdown 文件定字节预算，检查启动文件总量 |

## 快速开始

需要 bash 和 Python 3.10 或更高版本（在 3.12 上测试）。git 可选。

```bash
git clone <repo-url> context-governor
cd context-governor

# 1. 跑全部测试：在临时目录建一个示例工作区，在里面跑完所有检查，不会写入本仓库
bash scripts/run_tests.sh          # 等价于 python3 -m unittest discover -s tests -v

# 2. 自己建一个示例工作区看看
bash scripts/make_workspace.sh /tmp/cg-demo
cd /tmp/cg-demo
bash tools/context/run_context_governor_all.sh --root .
./管家                 # 看状态
./管家 下一步
./管家 我要改 BOOT.md   # 改动前检查
```

`run_context_governor_all.sh` 依次建索引、视图、BOOT、跑完整性审计、写任务状态、建启动包、跑启动预算、递归入口检测、改动控制检查和 16 个集成测试，最后写报告。判决不阻断时退出码为 0。

## 接入你自己的仓库

脚本假定工具放在被治理的工作区内部：`<workspace>/tools/context`、`tools/dev`、`tools/keeper`。所有命令在工作区根目录运行，或者传 `--root <workspace>`。

```bash
CG=/path/to/context-governor
WS=/path/to/your/workspace

mkdir -p "$WS/tools" "$WS/context"
cp -R "$CG/tools/context" "$CG/tools/dev" "$CG/tools/keeper" "$WS/tools/"
cp "$CG/tools/context_budget_check.py" "$WS/tools/"                 # 可选
cp -R "$CG/skills" "$CG/docs" "$WS/"                                # 可选
cp "$CG/ctx" "$CG/k" "$CG/管家" "$CG/上下文管家" "$WS/"              # 可选：中文入口
cp -n "$CG"/examples/workspace/context/* "$WS/context/"              # 起步配置，不覆盖已有文件，按需修改

cd "$WS"
bash tools/context/run_context_governor_all.sh --root .
```

最少只需要 `context/SYSTEM_INVARIANTS.json` 和 `context/CONTEXT_LOAD_POLICY.md`，其余文件第一次运行时生成。`var/` 下的审计输出会记录本机绝对路径，请在你的仓库里忽略它；`context/` 下的生成物（BOOT、任务状态、索引、注册表）每次运行都会重建，是否提交由你决定，本仓库 `.gitignore` 里列出了它们。

项目 ID `default` 是保留的：它代表工作区根目录本身，`BOOT.md`、`context/TASK_STATE.json` 和 `context/indexes/` 都属于它。其他项目用 `init_project_context.py` 注册，文件放在 `context/projects/<id>/`。注册表里，工作区内的项目根目录存成相对路径（根目录就是 `.`）。

## 配置：`context/SYSTEM_INVARIANTS.json`

| 字段 | 用途 |
|---|---|
| `rules` | 项目不变量。含 `boot_rule_keywords` 关键词的规则（最多 9 条）会写进 `BOOT.md` |
| `required_rules` | 必须出现在 `rules` 里的短语，由 `tools/dev/invariant_check.py` 检查；不写则用默认的两条（holdout 锁定、禁止递归入口） |
| `forbidden_claims` | `[{"id": ..., "pattern": <正则>}]`。`BOOT.md` 里出现匹配的说法即判为语义漂移；正则写错也会判失败 |
| `boot_rule_keywords` | 选哪些规则进 BOOT，默认 `holdout`、`side effect`、`recursive`、`boot.md` |
| `boot_limits` | BOOT 的 `max_lines` / `max_chars`，不能超过 80 / 4000 |
| `holdout_status_required` | 必须是 `LOCKED` |

示例见 `examples/workspace/context/SYSTEM_INVARIANTS.json`。预算（行数、字符数、视图行数等）的默认值在 `tools/context/governor_common.py` 的 `DEFAULT_BUDGET`，首次运行写到 `context/budgets/` 和 `context/projects/<id>/CONTEXT_BUDGET.json`。

## 检查会报告什么

| 检查 | 判决 | 输出 |
|---|---|---|
| 完整性审计 | `CONTEXT_INTEGRITY_PASS`，或 `CONTEXT_INTEGRITY_FAIL_BOOT_TOO_LARGE` / `_RECURSIVE_ENTRY` / `_STATE_TOO_LARGE` / `_HOLDOUT_RISK` / `_SEMANTIC_DRIFT` / `_MISSING_POINTER`（退出码 1） | `var/context_control_2026_06_23/audit/context_integrity_verdict.json` 和逐项 CSV |
| 启动预算 | `STARTUP_BUDGET_PASS`，或 `STARTUP_BUDGET_FAIL_FULL_INDEX_INCLUDED` / `_RAW_EVIDENCE_INCLUDED` / `_HOLDOUT_RISK` / `_MISSING_CURRENT_RUNNER` / `_TOO_LARGE`（退出码 2） | `var/context_governor_2026_06_24/audit/startup_budget_*` |
| 递归入口 | `RECURSIVE_ENTRY_PASS` / `RECURSIVE_ENTRY_FAIL`（退出码 2） | `var/context_governor_2026_06_24/audit/recursive_entry_scan.csv` |
| 读取闸门 | 正文（`mode: content`）、只给指针（`pointer_only`）或拒绝（`LARGE_FILE_REQUIRES_REASON`、`HOLDOUT_CONTENT_READ_DENIED` 等，退出码 2） | `context/read_logs/CONTEXT_READ_LOG.jsonl` |
| 改动前分级 | `LOW_RISK` / `RISK_REVIEW_REQUIRED` / `UNKNOWN_CHANGE_SURFACE`（没有 git 改动也没给 `--changed-file`） | `var/dev_change_control_2026_06_24/` |
| 继续执行 | 运行当前业务 runner；runner 缺失退出码 2，是治理脚本退出码 3，类型不支持退出码 4 | 写入 gap 队列 |
| 总控 | `MULTI_PROJECT_CONTEXT_GOVERNOR_BUILT_AND_VERIFIED`，或 `..._BLOCKED_*`（退出码 1） | `var/context_governor_2026_06_24/verdict.json`、报告、`audit/governor_run_steps.csv` |

gap 队列（`gap_queue.csv`）是追加的审计历史，测试故意制造的失败也会留在里面。当前是否有阻断以最终判决为准；Keeper 默认不把历史行当成当前失败。

## 常用命令

```bash
bash tools/context/start_project.sh default --root .        # 激活项目，打印启动包、当前 runner、下一步
bash tools/context/continue_project.sh default --root .     # 运行当前业务 runner
python3 tools/context/query_index.py --root . --index file --path-contains notes --limit 20
python3 tools/context/read_gate/read_context_file.py notes/design_notes.md --root . --reason "当前任务需要" --max-chars 12000
python3 tools/context/startup_budget_test.py --root .
python3 tools/context/recursive_entry_detector.py --root .
bash tools/dev/run_dev_checks.sh --root . --changed-file BOOT.md
bash tools/context/hooks/install_context_hooks.sh            # 安装 git pre-commit 检查
python3 tools/context_budget_check.py --root . --report var/context_budget/REPORT.md
```

注册另一个项目（可以在工作区外）：

```bash
python3 tools/context/project/init_project_context.py --root . \
  --project-id my_project --project-name "My Project" --project-root /path/to/my_project --activate
```

更多说明见 `docs/context/`、`docs/dev/` 和 `docs/keeper/`。

## Keeper（上下文管家）

```bash
./上下文管家                # 状态
./管家 现在做到哪了
./管家 打开项目
./管家 下一步
./管家 继续                 # 运行当前业务 runner；如果是治理脚本，只提示不执行
./管家 我要改 BOOT.md       # 改动前检查
./管家 帮我修一下入口        # 运行 run_context_control_all.sh 修复并验证
./管家 报告在哪里
python3 tools/keeper/keeper.py help
```

`bash tools/keeper/install.sh` 会把 `ck`、`context-keeper`、`上下文管家`、`管家` 以符号链接装进 `~/.local/bin`（可用 `KEEPER_BIN_DIR` 改），如果 `~/.npm-global/bin`、`~/.local/bin`、`~/bin` 中有已在 PATH 里的可写目录，也会装一份；并把 `skills/context_keeper` 链接到 `~/.codex/skills/context-keeper`（可用 `KEEPER_SKILL_DIR` 改）。它不会改 shell 配置文件，只会提示如何加 PATH。

## 测试

```bash
bash scripts/run_tests.sh
# 或
python3 -m unittest discover -s tests -v
# 装了 pytest 也可以直接 pytest
```

`tests/test_workspace.py` 先用 `scripts/make_workspace.sh` 在临时目录建一个示例工作区，然后在里面运行：5 个单元测试文件（10 个用例）、总控（17 步加首次运行的状态初始化，以及 16 个集成测试）、微内核总控、读取闸门、配置化的漂移规则、`continue` 拒绝治理 runner、改动前分级、Keeper 测试和 Markdown 预算检查。设 `KEEP_WORKSPACE=1` 可保留临时工作区。

## 限制

- 这是上下文治理和验证工具，不是操作系统级沙箱，也不是形式化的安全证明。读取闸门只对按约定调用它的 Agent 有效；Agent 仍然可以直接用 `cat` 等命令读文件。
- holdout、sealed、封存的判定看的是路径关键词；语义漂移和违禁内容靠正则，只能抓到写明的说法。
- 检查看文件名、路径、大小和文本模式，不理解内容是否正确。
- `var/` 下的审计输出会记录本机绝对路径，不要提交；注册在工作区之外的项目，其根目录也以绝对路径存进注册表。
- 输出目录名带日期（如 `var/context_governor_2026_06_24`），沿用最初版本的命名。
- 工具需要放在被治理的工作区内部（见“接入你自己的仓库”）。

## 项目历史

提交时间沿用作者本机的原始记录（澳大利亚东部时间）：

- 2026-06-24 02:53：Markdown 上下文预算检查。
- 2026-06-24 白天写成 Context Governor 和 Keeper，2026-07-04 18:51 第一次提交。
- 2026-07-10 05:20：预算检查把 `NORTH_STAR.md` 列为启动文件。
- 2026-10-05：开源整理。工具最初在一个私有工作区里使用；开源时把专用的项目名、规则和示例换成了中立内容，规则改为从配置读取，补了示例工作区、测试和文档。

## English

**Context Governor** keeps an AI coding agent's start-up context small and trustworthy. The agent starts from a budgeted, generated `BOOT.md`, a startup bundle and bounded index views. Full indexes are query-only, raw evidence is returned as pointers, and holdout or sealed paths are refused. Separate audits report blocking verdicts: an integrity audit (BOOT size and pointers, recursive entry files, forbidden BOOT content, semantic drift, holdout lock, authority ceiling), a startup budget test that blocks when a full index, raw evidence or holdout content leaks into startup context, and a recursive-entry detector. Change-control checks classify edits before they happen, and one orchestrator reruns every step and test with a step audit; the final report reads the integrity result from its own audit file, so reruns agree. **Keeper** is a Chinese command entry (`管家`, `上下文管家`, `ck`) over the same scripts.

Quick start: `bash scripts/run_tests.sh`, then `bash scripts/make_workspace.sh /tmp/cg-demo && cd /tmp/cg-demo && bash tools/context/run_context_governor_all.sh --root .`. Requires bash and Python 3.10+, standard library only. To use it in your own repository, copy `tools/` into it and start from `examples/workspace/context/`.

Limits: this is a context-governance and verification tool, not an OS-level sandbox or a formal security proof. Gates only bind agents that use them; holdout detection is path-based and drift detection is regex-based. Audit outputs under `var/` contain absolute local paths and should not be committed.

## License

MIT, see `LICENSE`.
