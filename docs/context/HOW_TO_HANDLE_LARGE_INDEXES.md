# 如何处理大索引

启动阶段只读：

```text
context/indexes/views/*_VIEW.csv
```

需要查全量索引时使用：

```bash
python3 tools/context/query_index.py \
  --root <workspace> \
  --index file \
  --project default \
  --path-contains tools/context \
  --limit 20
```

索引规则：

- `views` 是启动安全读集。
- `shards` 是按项目、artifact type、phase 切分的窄读集。
- 全量 `context/indexes/*.csv` 是查询底座，不是启动读物。
- 每次全量索引重建后都要运行 `tools/context/build_index_views.py`。
