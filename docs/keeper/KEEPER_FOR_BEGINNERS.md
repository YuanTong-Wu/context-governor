# 给第一次使用者的上下文管家说明

你不需要直接读 `context/`、`TASK_STATE.json`、`FILE_INDEX.csv` 或 `GAP_INDEX.csv`。

先安装短命令：

```bash
bash tools/keeper/install.sh
```

从这三个命令开始：

```bash
管家 打开项目
上下文管家
管家 下一步
```

如果你准备改入口、脚本、项目登记表或治理文件，先运行：

```bash
管家 我要改 <你要改的文件>
```

如果状态显示入口系统需要修复，运行：

```bash
管家 帮我修一下入口
```

`gap_queue.csv` 里可能有回归测试故意制造的历史行。上下文管家默认不把这些历史测试行显示成当前失败；只有 final verdict 或当前状态显示 active blocker 时，才会提醒你。
