# 上下文管家常用命令

## 最短命令

```bash
上下文管家
管家 现在做到哪了
管家 打开项目
管家 下一步
管家 继续
管家 我要改 BOOT.md
管家 帮我修一下入口
管家 报告在哪里
```

英文短别名也保留：

```bash
ck
ck 状态
ck 打开
ck 下一步
ck 继续
ck 改 BOOT.md
ck 修
ck 报告
```

如果还没有安装 `ck`：

```bash
bash tools/keeper/install.sh
```

## 打开项目

```bash
python tools/keeper/keeper.py open
```

## 查看当前状态

```bash
python tools/keeper/keeper.py status
```

## 查看下一步

```bash
python tools/keeper/keeper.py next
```

## 继续当前业务 runner

```bash
python tools/keeper/keeper.py continue
```

如果当前 runner 是 governor/control runner，keeper 会友好提示当前没有业务 runner，而不是写一堆递归阻塞。先设置业务 runner：

```bash
python3 tools/context/project/set_project_runner.py tools/jobs/run_daily.sh   # 当前项目
python3 tools/context/project/set_project_runner.py --clear                  # 取消
```

## 改动前检查

```bash
python tools/keeper/keeper.py check-change --changed-file tools/context/start_project.sh
python tools/keeper/keeper.py check-change --changed-file BOOT.md --changed-file context/global/PROJECT_REGISTRY.json
```

## 修复/验证入口系统

```bash
python tools/keeper/keeper.py fix
```

这会调用现有 `run_context_control_all.sh`，不是新增治理逻辑。

## 查看报告

```bash
python tools/keeper/keeper.py report
```
