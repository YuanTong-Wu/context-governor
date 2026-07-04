#!/usr/bin/env python3
import json
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def run_cmd(args: list[str], cwd: Path = ROOT, expect: int = 0) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(args, cwd=cwd, text=True, capture_output=True, timeout=120)
    if proc.returncode != expect:
        raise SystemExit(
            f"command failed: {' '.join(args)}\nexpected={expect} got={proc.returncode}\n{proc.stdout}\n{proc.stderr}"
        )
    return proc


def assert_contains(text: str, needle: str) -> None:
    if needle not in text:
        raise SystemExit(f"expected output to contain {needle!r}, got:\n{text}")


def main() -> int:
    help_out = run_cmd(["python3", "tools/keeper/keeper.py", "help"]).stdout
    assert_contains(help_out, "上下文管家命令")
    assert_contains(help_out, "不打开 holdout")
    assert_contains(help_out, "管家 下一步")

    default_out = run_cmd(["python3", "tools/keeper/keeper.py"]).stdout
    assert_contains(default_out, "上下文管家状态")

    status_out = run_cmd(["./管家", "现在做到哪了"]).stdout
    for needle in ["当前项目", "入口状态", "BOOT 行数", "启动包状态", "holdout 状态", "最新判决", "当前最大 active blocker"]:
        assert_contains(status_out, needle)
    assert_contains(status_out, "历史测试 gap 默认隐藏")

    next_out = run_cmd(["./上下文管家", "下一步"]).stdout
    assert_contains(next_out, "下一步建议")

    continue_out = run_cmd(["python3", "tools/keeper/keeper.py", "管家", "继续"]).stdout
    assert_contains(continue_out, "上下文系统已经健康，当前没有业务 runner")

    report_out = run_cmd(["python3", "tools/keeper/keeper.py", "管家", "报告在哪里"]).stdout
    assert_contains(report_out, "默认不展示完整索引和完整 gap queue")

    with tempfile.TemporaryDirectory(prefix="keeper-empty-root-") as tmp:
        unknown = run_cmd(["python3", "tools/keeper/keeper.py", "--root", tmp, "check-change"]).stdout
        assert_contains(unknown, "UNKNOWN_CHANGE_SURFACE")
        summary = json.loads((Path(tmp) / "var/dev_change_control_2026_06_24/preflight_change_summary.json").read_text())
        if summary.get("verdict") != "UNKNOWN_CHANGE_SURFACE":
            raise SystemExit("check-change should write UNKNOWN_CHANGE_SURFACE summary for empty root")

    explicit = run_cmd(
        [
            "python3",
            "tools/keeper/keeper.py",
            "管家",
            "我要改",
            "BOOT.md",
            "tools/keeper/keeper.py",
        ]
    ).stdout
    assert_contains(explicit, "改动前检查：")

    verdict = json.loads((ROOT / "var/context_keeper/verdict.json").read_text())
    if not str(verdict.get("keeper_verdict", "")).startswith("CONTEXT_KEEPER_"):
        raise SystemExit("keeper verdict should be written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
