# 如何使用上下文管家

上下文管家是 `Context Governor` 的中文小白入口。它不替代底层治理脚本，只把常用动作翻译成少量安全命令。

最省事的用法是安装短命令：

```bash
bash tools/keeper/install.sh
```

安装后日常可以直接用中文：

```bash
上下文管家
管家 现在做到哪了
管家 下一步
管家 继续
管家 我要改 BOOT.md
管家 帮我修一下入口
管家 报告在哪里
```

## 常用入口

```bash
python tools/keeper/keeper.py open
python tools/keeper/keeper.py status
python tools/keeper/keeper.py next
python tools/keeper/keeper.py continue
python tools/keeper/keeper.py check-change --changed-file BOOT.md
python tools/keeper/keeper.py fix
python tools/keeper/keeper.py report
```

也可以使用：

```bash
bash tools/keeper/keeper.sh status
```

在项目根目录也可以直接用：

```bash
./k
./k 下一步
./ctx 状态
./上下文管家
./管家 现在做到哪了
```

## 安全边界

- 不打开 holdout。
- 不输出完整大索引。
- 不输出完整 gap queue。
- 不执行外部副作用动作（支付、部署、账户变更）。
- 不扩写 `BOOT.md`。

## 状态怎么看

`status` 会给出当前项目、入口状态、`BOOT.md` 行数、启动包状态、holdout 状态、当前阶段、最新判决、当前最大 active blocker、下一步建议和最新报告路径。

如果底层 `current_runner` 是 governor runner，`continue` 会提示“上下文系统已经健康，当前没有业务 runner”和设置方法，不会递归执行 governor。业务 runner 用 `python3 tools/context/project/set_project_runner.py tools/<runner>.sh` 设置（默认设置当前项目），之后 `continue` 就会运行它。
