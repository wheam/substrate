# zones — minimal 示例的分区注册表

> 顶部可解析 YAML 块；字段契约见引擎 `schemas/zone.schema.yaml`。本示例只开两个 zone。

```yaml
zones:
  - id: knowledge
    path: knowledge/
    purpose: 互链知识页（本示例：技术概念）
    schema: knowledge-zone-v1
    maintainer_skill: substrate-curator
    readers: [all]
    writers: [all]
    disposition: canonical
    privacy: private

  - id: collections
    path: collections/
    purpose: 通用收藏（行式 canonical + 人读分片）
    schema: collection-zone-v1
    maintainer_skill: substrate-collections
    readers: [all]
    writers: [all]
    disposition: canonical
    privacy: private
    graduation: "rows>2000 → 分片 JSONL；需 join → 本地 SQLite 缓存"
```

---

- **knowledge/**：见 `../knowledge/README.md`。
- **collections/**：见 `../collections/tools/tools.md`。
