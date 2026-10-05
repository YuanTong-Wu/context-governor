# Context Recursion Ban

1. Do not create `BOOT_FOR_BOOT.md`.
2. Do not create `START_HERE_FOR_START_HERE.md`.
3. Do not create `README_FOR_BOOT.md`.
4. Do not create `ENTRYPOINT_SUMMARY_OF_ENTRYPOINT.md`.
5. Do not explain one entry file by creating a shorter entry file.
6. Do not summarize a summary.
7. Do not expand `BOOT.md` into a project report.
8. Do not expand `context/TASK_STATE.json` into a historical summary.
9. Do not expand `context/CURRENT_VERDICT.json` into a full report.
10. If `BOOT.md` needs more detail, update indexes or source files instead.
11. If the agent does not know the next step, read `context/TASK_STATE.json` and the gap index view.
12. If context is too long, write a checkpoint or compress the active task state.
13. If compressed context conflicts with source manifests, return to the source manifest.
14. If the entry file expands, treat context architecture as failed and run repair.
