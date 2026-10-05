#!/usr/bin/env python3
"""Chinese-friendly wrapper for the local Context Governor."""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


KEEPER_DIR = Path("var/context_keeper")
KEEPER_GAP_FIELDS = [
    "gap_id",
    "command",
    "project_id",
    "gap_type",
    "severity",
    "blocking_level",
    "observed_status",
    "expected_status",
    "next_action",
    "created_at_utc",
    "notes",
]

GOVERNOR_RUNNERS = {
    "tools/context/run_context_governor_all.sh",
    "tools/context/run_context_control_all.sh",
    "tools/context/start_project.sh",
    "tools/context/continue_project.sh",
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(root: Path, path: Path | str) -> str:
    p = Path(path)
    try:
        return str(p.resolve().relative_to(root.resolve()))
    except Exception:
        return str(path)


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def ensure_keeper_files(root: Path) -> None:
    keeper_dir = root / KEEPER_DIR
    keeper_dir.mkdir(parents=True, exist_ok=True)
    gap = keeper_dir / "gap_queue.csv"
    if not gap.exists():
        with gap.open("w", encoding="utf-8", newline="") as handle:
            csv.DictWriter(handle, fieldnames=KEEPER_GAP_FIELDS).writeheader()
    next_actions = keeper_dir / "next_actions.md"
    if not next_actions.exists():
        next_actions.write_text("# Context Keeper Next Actions\n\n- 运行 `python tools/keeper/keeper.py status` 查看当前状态。\n", encoding="utf-8")


def append_keeper_gap(root: Path, row: dict[str, str]) -> None:
    ensure_keeper_files(root)
    path = root / KEEPER_DIR / "gap_queue.csv"
    rows: list[dict[str, str]] = []
    if path.exists():
        with path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
    body = dict(row)
    body.setdefault("gap_id", f"keeper_gap_{abs(hash(json.dumps(body, ensure_ascii=False, sort_keys=True))) & 0xffffffff:x}")
    body.setdefault("created_at_utc", utc_now())
    rows.append(body)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=KEEPER_GAP_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for item in rows[-50:]:
            writer.writerow({key: item.get(key, "") for key in KEEPER_GAP_FIELDS})


def active_project_id(root: Path) -> str:
    active = read_json(root / "context/global/ACTIVE_PROJECT.json", {})
    return str(active.get("active_project_id") or active.get("project_id") or "default")


def project_alias(value: str | None) -> str:
    if not value or value in {"default", "默认"}:
        return "default"
    return value


def load_project(root: Path, project_id: str | None = None) -> dict[str, Any]:
    registry = read_json(root / "context/global/PROJECT_REGISTRY.json", {}) or {}
    projects = registry.get("projects") or {}
    pid = project_alias(project_id) if project_id else active_project_id(root)
    project = projects.get(pid) or {}
    project.setdefault("project_id", pid)
    project.setdefault("project_name", pid)
    project.setdefault("project_root", str(root))
    project.setdefault("boot_path", "BOOT.md")
    project.setdefault("state_path", "context/TASK_STATE.json")
    project.setdefault("verdict_path", "context/CURRENT_VERDICT.json")
    project.setdefault("startup_bundle_path", f"context/generated/startup_bundles/{pid}_STARTUP_BUNDLE.md")
    project.setdefault("holdout_policy", "LOCKED")
    return project


def project_path(root: Path, project: dict[str, Any], key: str) -> Path:
    value = str(project.get(key, ""))
    path = Path(value)
    if path.is_absolute():
        return path
    return root / path


def line_count(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        return sum(1 for _ in handle)


def char_count(path: Path) -> int:
    if not path.exists():
        return 0
    return len(path.read_text(encoding="utf-8", errors="replace"))


def read_state(root: Path, project: dict[str, Any]) -> dict[str, Any]:
    return read_json(project_path(root, project, "state_path"), {}) or {}


def latest_verdict(root: Path) -> dict[str, Any]:
    governor = read_json(root / "var/context_governor_2026_06_24/verdict.json", None)
    if isinstance(governor, dict) and governor:
        return governor | {"_source": "var/context_governor_2026_06_24/verdict.json"}
    control = read_json(root / "var/context_control_2026_06_23/verdict.json", None)
    if isinstance(control, dict) and control:
        return control | {"_source": "var/context_control_2026_06_23/verdict.json"}
    current = read_json(root / "context/CURRENT_VERDICT.json", {}) or {}
    return current | {"_source": "context/CURRENT_VERDICT.json"}


def startup_budget_verdict(root: Path, project_id: str) -> str:
    """Latest startup budget verdict for this project, or UNKNOWN when it was last run for another one."""
    verdict = read_json(root / "var/context_governor_2026_06_24/audit/startup_budget_verdict.json", None)
    if isinstance(verdict, dict) and verdict.get("verdict") and verdict.get("project_id", project_id) == project_id:
        return str(verdict["verdict"])
    return "UNKNOWN"


def active_blocker(root: Path, verdict: dict[str, Any]) -> str:
    if not verdict.get("hard_blocker") and not verdict.get("failures"):
        return "无当前 active blocker（历史测试 gap 默认隐藏）"
    failures = verdict.get("failures") or []
    if failures:
        first = failures[0]
        if isinstance(first, dict):
            return str(first.get("check_id") or first.get("reason") or first)
        return str(first)
    blocked = root / "var/context_governor_2026_06_24/blocked_reason.csv"
    if blocked.exists():
        with blocked.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        if rows:
            row = rows[-1]
            return f"{row.get('reason', 'UNKNOWN')} @ {row.get('artifact_path', '')}"
    return "存在 hard_blocker，但未找到可读 blocker 详情"


def next_suggestion(state: dict[str, Any], verdict: dict[str, Any]) -> str:
    runner = str(state.get("current_runner") or "")
    if verdict.get("hard_blocker"):
        return "先运行 `python tools/keeper/keeper.py report` 查看报告，再按报告修复。"
    if runner in GOVERNOR_RUNNERS:
        return "上下文系统已经健康，当前没有业务 runner。需要继续业务时，先用 `python3 tools/context/project/set_project_runner.py tools/<你的 runner>.sh` 设置业务 runner。"
    if runner:
        return "可以运行 `python tools/keeper/keeper.py continue` 执行当前业务 runner。"
    return str(state.get("next_allowed_action") or "运行 `python tools/keeper/keeper.py open` 初始化项目。")


def report_path(root: Path, verdict: dict[str, Any]) -> str:
    for key in ("report_path", "latest_report_path"):
        if verdict.get(key):
            return str(verdict[key])
    p0 = root / "var/context_governor_p0_fix_2026_06_24/reports/P0_FIX_REPORT.md"
    if p0.exists():
        return rel(root, p0)
    return "未找到报告"


def collect_status(root: Path, project_id: str | None = None) -> dict[str, Any]:
    project = load_project(root, project_id)
    pid = str(project["project_id"])
    state = read_state(root, project)
    verdict = latest_verdict(root)
    boot = project_path(root, project, "boot_path")
    bundle = project_path(root, project, "startup_bundle_path")
    boot_lines = line_count(boot)
    budget = startup_budget_verdict(root, pid)
    entry_ok = boot.exists() and boot_lines <= 80 and bundle.exists() and budget == "STARTUP_BUDGET_PASS" and not verdict.get("hard_blocker")
    bundle_status = "存在" if bundle.exists() else "缺失"
    if bundle.exists():
        bundle_status = f"存在，{char_count(bundle)} chars，budget={budget}"
    return {
        "project_id": pid,
        "project_name": project.get("project_name", pid),
        "entry_status": "健康" if entry_ok else "需要检查",
        "boot_lines": boot_lines,
        "startup_bundle_status": bundle_status,
        "startup_bundle_path": rel(root, bundle),
        "holdout_status": state.get("holdout_status") or project.get("holdout_policy") or "UNKNOWN",
        "current_phase": state.get("current_phase", "UNKNOWN"),
        "current_runner": state.get("current_runner", ""),
        "latest_verdict": verdict.get("verdict", "UNKNOWN"),
        "latest_verdict_source": verdict.get("_source", ""),
        "hard_blocker": bool(verdict.get("hard_blocker")),
        "active_blocker": active_blocker(root, verdict),
        "next_action": next_suggestion(state, verdict),
        "latest_report_path": report_path(root, verdict),
    }


def write_keeper_outputs(root: Path, command: str, status: dict[str, Any], keeper_verdict: str = "CONTEXT_KEEPER_READY") -> None:
    ensure_keeper_files(root)
    summary = {
        "command": command,
        "created_at_utc": utc_now(),
        "project_id": status.get("project_id"),
        "entry_status": status.get("entry_status"),
        "latest_context_verdict": status.get("latest_verdict"),
        "active_blocker": status.get("active_blocker"),
        "next_action": status.get("next_action"),
        "verdict": keeper_verdict,
    }
    verdict = {
        "created_at_utc": summary["created_at_utc"],
        "project_id": status.get("project_id"),
        "hard_blocker": keeper_verdict.endswith("BLOCKED"),
        "keeper_verdict": keeper_verdict,
        "context_verdict": status.get("latest_verdict"),
        "report_path": status.get("latest_report_path"),
        "summary_path": "var/context_keeper/summary.json",
    }
    write_json(root / KEEPER_DIR / "summary.json", summary)
    write_json(root / KEEPER_DIR / "verdict.json", verdict)
    (root / KEEPER_DIR / "next_actions.md").write_text(
        "# Context Keeper Next Actions\n\n"
        f"- 当前项目：`{status.get('project_id')}`\n"
        f"- 下一步建议：{status.get('next_action')}\n"
        f"- 最新报告：`{status.get('latest_report_path')}`\n",
        encoding="utf-8",
    )


def print_status(status: dict[str, Any]) -> None:
    print("上下文管家状态")
    print(f"1. 当前项目：{status['project_id']}（{status['project_name']}）")
    print(f"2. 入口状态：{status['entry_status']}")
    print(f"3. BOOT 行数：{status['boot_lines']}")
    print(f"4. 启动包状态：{status['startup_bundle_status']}")
    print(f"5. holdout 状态：{status['holdout_status']}")
    print(f"6. 当前阶段：{status['current_phase']}")
    print(f"7. 最新判决：{status['latest_verdict']}（hard_blocker={str(status['hard_blocker']).lower()}）")
    print(f"8. 当前最大 active blocker：{status['active_blocker']}")
    print(f"9. 下一步建议：{status['next_action']}")
    print(f"10. 最新报告路径：{status['latest_report_path']}")


def run(root: Path, args: list[str], timeout: int = 300) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=root, text=True, capture_output=True, timeout=timeout)


def command_open(root: Path, args: argparse.Namespace) -> int:
    project_id = project_alias(args.project)
    cmd = ["bash", "tools/context/start_project.sh", project_id, "--root", str(root)]
    if args.project_root:
        cmd += ["--project-root", args.project_root]
    if args.project_name:
        cmd += ["--project-name", args.project_name]
    proc = run(root, cmd, timeout=300)
    status = collect_status(root, project_id)
    if proc.returncode == 0:
        write_keeper_outputs(root, "open", status, "CONTEXT_KEEPER_OPENED")
        print(f"已打开项目：{status['project_id']}")
        print(f"启动包：{status['startup_bundle_path']}")
        print(f"下一步：{status['next_action']}")
        return 0
    append_keeper_gap(root, {
        "command": "open",
        "project_id": project_id,
        "gap_type": "open_project_failed",
        "severity": "HIGH",
        "blocking_level": "BLOCKING",
        "observed_status": f"exit_code={proc.returncode}",
        "expected_status": "exit_code=0",
        "next_action": "查看底层 start_project 输出并修复后重试",
        "notes": (proc.stderr or proc.stdout)[-1000:],
    })
    write_keeper_outputs(root, "open", status, "CONTEXT_KEEPER_BLOCKED")
    print("打开项目失败。已记录到 var/context_keeper/gap_queue.csv。")
    return proc.returncode or 1


def command_status(root: Path, args: argparse.Namespace) -> int:
    status = collect_status(root, args.project_id)
    write_keeper_outputs(root, "status", status)
    print_status(status)
    return 0


def command_next(root: Path, args: argparse.Namespace) -> int:
    status = collect_status(root, args.project_id)
    write_keeper_outputs(root, "next", status)
    print(f"下一步建议：{status['next_action']}")
    print(f"参考报告：{status['latest_report_path']}")
    return 0


def command_continue(root: Path, args: argparse.Namespace) -> int:
    status = collect_status(root, args.project_id)
    runner = str(status.get("current_runner") or "")
    if runner in GOVERNOR_RUNNERS:
        write_keeper_outputs(root, "continue", status, "CONTEXT_KEEPER_NO_BUSINESS_RUNNER")
        print("上下文系统已经健康，当前没有业务 runner。")
        print("设置方法：python3 tools/context/project/set_project_runner.py tools/<你的 runner>.sh")
        return 0
    if not runner:
        write_keeper_outputs(root, "continue", status, "CONTEXT_KEEPER_NO_BUSINESS_RUNNER")
        print("当前没有业务 runner。")
        print("设置方法：python3 tools/context/project/set_project_runner.py tools/<你的 runner>.sh")
        return 0
    proc = run(root, ["bash", "tools/context/continue_project.sh", status["project_id"], "--root", str(root)], timeout=300)
    refreshed = collect_status(root, args.project_id)
    if proc.returncode == 0:
        write_keeper_outputs(root, "continue", refreshed, "CONTEXT_KEEPER_CONTINUE_PASS")
        print("当前业务 runner 已执行完成。")
        print(f"下一步：{refreshed['next_action']}")
        return 0
    append_keeper_gap(root, {
        "command": "continue",
        "project_id": status["project_id"],
        "gap_type": "continue_failed",
        "severity": "HIGH",
        "blocking_level": "BLOCKING",
        "observed_status": f"exit_code={proc.returncode}",
        "expected_status": "exit_code=0",
        "next_action": "运行 report 查看底层报告，修复 runner 后重试",
        "notes": (proc.stderr or proc.stdout)[-1000:],
    })
    write_keeper_outputs(root, "continue", refreshed, "CONTEXT_KEEPER_BLOCKED")
    print("继续执行失败。已记录到 var/context_keeper/gap_queue.csv。")
    return proc.returncode or 1


def command_check_change(root: Path, args: argparse.Namespace) -> int:
    script = repo_root() / "tools/dev/preflight_change.py"
    cmd = ["python3", str(script), "--root", str(root)]
    for changed in args.changed_file or []:
        cmd += ["--changed-file", changed]
    proc = subprocess.run(cmd, cwd=repo_root(), text=True, capture_output=True, timeout=120)
    status = collect_status(root, args.project_id)
    verdict = (proc.stdout.strip().splitlines() or ["CHECK_FAILED"])[-1]
    keeper_verdict = "CONTEXT_KEEPER_CHANGE_CHECK_PASS" if proc.returncode == 0 else "CONTEXT_KEEPER_BLOCKED"
    write_keeper_outputs(root, "check-change", status, keeper_verdict)
    print(f"改动前检查：{verdict}")
    print("结果路径：var/dev_change_control_2026_06_24/preflight_change.csv")
    print("摘要路径：var/dev_change_control_2026_06_24/preflight_change_summary.json")
    if verdict == "UNKNOWN_CHANGE_SURFACE":
        print("提示：未检测到 git diff，也没有传入 --changed-file；请补充改动文件或人工确认改动面。")
    return proc.returncode


def command_fix(root: Path, args: argparse.Namespace) -> int:
    proc = run(root, ["bash", "tools/context/run_context_control_all.sh", "--root", str(root)], timeout=300)
    status = collect_status(root, args.project_id)
    if proc.returncode == 0:
        write_keeper_outputs(root, "fix", status, "CONTEXT_KEEPER_FIX_PASS")
        print("入口系统已修复/验证完成。")
        print(f"最新判决：{status['latest_verdict']}")
        print(f"报告：{status['latest_report_path']}")
        return 0
    append_keeper_gap(root, {
        "command": "fix",
        "project_id": status["project_id"],
        "gap_type": "fix_failed",
        "severity": "HIGH",
        "blocking_level": "BLOCKING",
        "observed_status": f"exit_code={proc.returncode}",
        "expected_status": "exit_code=0",
        "next_action": "查看 context control 报告并修复后重试",
        "notes": (proc.stderr or proc.stdout)[-1000:],
    })
    write_keeper_outputs(root, "fix", status, "CONTEXT_KEEPER_BLOCKED")
    print("入口系统修复失败。已记录到 var/context_keeper/gap_queue.csv。")
    return proc.returncode or 1


def command_report(root: Path, args: argparse.Namespace) -> int:
    status = collect_status(root, args.project_id)
    write_keeper_outputs(root, "report", status)
    print("可读报告")
    print(f"- 最新报告：{status['latest_report_path']}")
    p0 = root / "var/context_governor_p0_fix_2026_06_24/reports/P0_FIX_REPORT.md"
    if p0.exists():
        print(f"- P0 修复报告：{rel(root, p0)}")
    governor = root / "var/context_governor_2026_06_24/reports/MULTI_PROJECT_CONTEXT_GOVERNOR_REPORT_2026_06_24.md"
    if governor.exists():
        print(f"- Governor 报告：{rel(root, governor)}")
    control = root / "var/context_control_2026_06_23/reports/CONTEXT_MICROKERNEL_REPORT_2026_06_23.md"
    if control.exists():
        print(f"- Microkernel 报告：{rel(root, control)}")
    print("默认不展示完整索引和完整 gap queue。需要审计时再直接打开对应文件。")
    return 0


def command_help(root: Path, args: argparse.Namespace) -> int:
    status = collect_status(root, args.project_id)
    write_keeper_outputs(root, "help", status)
    print("上下文管家命令")
    print("  上下文管家                 # 查看状态")
    print("  管家 现在做到哪了           # 查看状态")
    print("  管家 打开项目              # 打开默认项目")
    print("  管家 下一步                 # 查看下一步")
    print("  管家 继续                   # 继续当前业务 runner")
    print("  管家 我要改 BOOT.md         # 改动前检查")
    print("  管家 帮我修一下入口          # 修复/验证入口系统")
    print("  管家 报告在哪里             # 查看报告")
    print("")
    print("短英文别名也可用：")
    print("  ck")
    print("  ck 下一步")
    print("")
    print("完整工程形式仍可用：")
    print("  python tools/keeper/keeper.py status")
    print("  python tools/keeper/keeper.py check-change --changed-file BOOT.md")
    print("安全边界：不打开 holdout，不输出完整大索引，不执行外部副作用动作。")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Context Keeper / 上下文管家", add_help=False)
    parser.add_argument("--root", default=str(repo_root()))
    sub = parser.add_subparsers(dest="command")

    open_p = sub.add_parser("open")
    open_p.add_argument("project", nargs="?", default="default")
    open_p.add_argument("--project-root")
    open_p.add_argument("--project-name")
    open_p.set_defaults(func=command_open)

    for name, func in [
        ("status", command_status),
        ("next", command_next),
        ("continue", command_continue),
        ("report", command_report),
        ("help", command_help),
    ]:
        p = sub.add_parser(name)
        p.add_argument("--project-id")
        p.set_defaults(func=func)

    check = sub.add_parser("check-change")
    check.add_argument("--project-id")
    check.add_argument("--changed-file", action="append", default=[])
    check.set_defaults(func=command_check_change)

    fix = sub.add_parser("fix")
    fix.add_argument("--project-id")
    fix.set_defaults(func=command_fix)
    return parser


def normalize_command(argv: list[str]) -> list[str]:
    leading: list[str] = []
    rest = list(argv)
    if rest[:1] == ["--root"] and len(rest) >= 2:
        leading = rest[:2]
        rest = rest[2:]
    if not rest:
        return leading + ["status"]

    rest = [item.strip() for item in rest if item.strip()]
    aliases_to_ignore = {"上下文管家", "管家", "上下文", "小管家", "keeper", "contextkeeper", "context-keeper"}
    while rest and rest[0].strip("，,。:： ") in aliases_to_ignore:
        rest = rest[1:]
    if not rest:
        return leading + ["status"]

    text = " ".join(rest)
    text = re.sub(r"[，,。？?！!；;：:]+", " ", text).strip()
    words = [item for item in text.split() if item]
    first = words[0] if words else ""
    joined = " ".join(words)
    aliases = {
        "状态": "status",
        "status": "status",
        "现在": "status",
        "做到哪": "status",
        "打开": "open",
        "启动": "open",
        "open": "open",
        "下一步": "next",
        "next": "next",
        "继续": "continue",
        "continue": "continue",
        "改": "check-change",
        "检查": "check-change",
        "改动": "check-change",
        "改动检查": "check-change",
        "check-change": "check-change",
        "修": "fix",
        "修复": "fix",
        "fix": "fix",
        "报告": "report",
        "report": "report",
        "帮助": "help",
        "help": "help",
    }
    command = aliases.get(first)
    if command is None:
        if any(needle in joined for needle in ["下一步", "接下来", "该干嘛", "该做什么", "下一件事"]):
            command = "next"
        elif any(needle in joined for needle in ["继续", "接着", "往下做", "上次任务"]):
            command = "continue"
        elif any(needle in joined for needle in ["报告", "结果", "审查", "在哪里"]):
            command = "report"
        elif any(needle in joined for needle in ["修复", "修一下", "修入口", "验证入口", "修系统"]):
            command = "fix"
        elif any(needle in joined for needle in ["打开", "启动", "进入", "切到", "切换"]):
            command = "open"
        elif any(needle in joined for needle in ["我要改", "准备改", "改 ", "改动", "检查影响", "改前", "变更"]):
            command = "check-change"
        elif any(needle in joined for needle in ["状态", "做到哪", "现在", "怎么样", "健康吗", "在哪"]):
            command = "status"
        else:
            command = first

    tail = words[1:]
    if command == "open":
        tail = ["default"] if not tail else [tail[0]]
        if tail and tail[0].lower() in {"default", "项目", "默认项目"}:
            tail = ["default"]
    if command == "check-change" and not any(item.startswith("-") for item in tail):
        file_tokens = [
            item.strip("`'\"“”‘’")
            for item in words
            if (
                "/" in item
                or "." in item
                or item.endswith((".md", ".py", ".sh", ".json", ".csv", ".txt"))
            )
        ]
        tail = file_tokens
    if command == "check-change" and tail and not any(item.startswith("-") for item in tail):
        expanded: list[str] = []
        for item in tail:
            if item in {"我要", "准备", "改", "改动", "检查", "影响", "一下", "文件"}:
                continue
            expanded.extend(["--changed-file", item])
        tail = expanded
    return leading + [command] + tail


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    argv = normalize_command(list(sys.argv[1:] if argv is None else argv))
    args = parser.parse_args(argv)
    root = Path(args.root).expanduser().resolve()
    ensure_keeper_files(root)
    if not hasattr(args, "func"):
        return command_help(root, argparse.Namespace(project_id=None))
    return int(args.func(root, args))


if __name__ == "__main__":
    raise SystemExit(main())
