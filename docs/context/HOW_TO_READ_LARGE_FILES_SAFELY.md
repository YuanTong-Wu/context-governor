# 如何安全读取大文件

默认不要直接打开大文件。使用读取闸门：

```bash
python3 tools/context/read_gate/read_context_file.py path/to/file.md \
  --root <workspace> \
  --reason "active task requires this section" \
  --max-chars 12000
```

## 规则

- 大文件必须提供 `--reason`，并设置 `--max-chars` 或 `--line-range`。
- raw evidence 默认只返回指针；如确需内容，必须显式 `--allow-raw-content`。
- holdout、sealed、封存路径默认拒绝读取。
- 所有读取都会写入 `context/read_logs/CONTEXT_READ_LOG.jsonl`。
