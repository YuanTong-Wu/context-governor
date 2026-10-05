# Context Budget Policy

Last updated: 2026-06-24

The chat compression window is smaller than this repository. The repository
therefore needs durable context budgets, not just better notes.

## Targets

| Role | Target |
|---|---:|
| Single startup file | 8 KiB |
| Active index | 10 KiB |
| Domain/archive index | 15 KiB |
| Handoff/current-work note | 12 KiB |
| Long memory or state file before indexing pressure | 25 KiB |
| Startup pack total | 40 KiB |

Startup pack means:

- `AGENTS.md`
- `NORTH_STAR.md`
- `README.md`
- `context/STARTUP_CONTEXT.md`
- `context/INDEX_ACTIVE.md`
- `context/INDEX_DOMAINS.md`
- `START_HERE_MEMORY.md`

## Policy

- Startup files should route, not explain everything.
- Large source files need compact indexes and targeted read commands.
- Generated inventories and upload packs should be parsed or searched, not
  pasted into chat.
- A file can exceed budget if it is deliberately non-startup and has a compact
  index.
- New long files should include a short index or be referenced from one.

## Verification

Run from the workspace root (or pass `--root <workspace>`). The config is read
from `context/context_budget.json`; without it the built-in defaults apply.

```bash
python3 tools/context_budget_check.py --report var/context_budget/CONTEXT_BUDGET_REPORT.md
```

For strict checks:

```bash
python3 tools/context_budget_check.py --fail-on-over-budget
```
