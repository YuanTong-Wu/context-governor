# Context Load Policy

1. Start every agent session by reading `BOOT.md`.
2. Then read `context/TASK_STATE.json`.
3. Then read `context/CURRENT_VERDICT.json`.
4. Then read the active project's startup bundle under `context/generated/startup_bundles/`.
5. Use the index views in `context/indexes/views/` for orientation.
6. Query full indexes only with `tools/context/query_index.py`.
7. Read only the schema and manifest fields needed by the current runner.
8. Read only the case card needed for the current task.
9. Read raw evidence only for audit, fingerprint mismatch, or evidence recheck.
10. Do not read archived history by default.
11. When context is insufficient, write a checkpoint instead of lengthening the entry file.
12. When the entry file grows, run `tools/context/context_integrity_check.py`; do not create a second entry file.
13. Do not depend on chat memory to recover project state.
14. Recovery must use `BOOT.md`, `context/TASK_STATE.json`, indexes, and manifests.
