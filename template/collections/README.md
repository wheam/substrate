# collections — 通用收藏

> **Agent Packet**
> - zone: collections
> - 维护 skill: `substrate-collections`
> - canonical: 每个收藏的**行式主表**（`<name>/data.csv` 或 `.jsonl`）= 单一事实源
> - 写前查: 主表里是否已有该条（按稳定 id/slug 去重）
> - 写后更新: ① 追加/改主表行；② 更新对应人读分片页；③ 同步本 README 索引
> - doctor 检查: 主表每行有稳定 id；分片页与主表条数对得上；`graduation` 阈值是否越线

## 结构

```
collections/
└── <name>/
    ├── data.csv          # 行式 canonical 主表（单一事实源，便于将来筛选/毕业）
    ├── <name>.md         # 本收藏的索引页（规则 + 查询入口 + 常用索引）
    └── by-<dim>/         # 人读分片（按城市/地区/分类…），只是索引，不是事实源
```

## 原则

- **先进主表**：每条先写进 `data.csv`（固定字段，含稳定 `id` slug）；分片页只是方便人看的视图。
- **不要过早拆碎**：某维度特别多了再拆分片（如 `by-cuisine/`）。
- **毕业**：行数越 `zones.md` 里该 zone 的 `graduation` 阈值时，doctor 会提议（CSV→分片 JSONL → 本地 SQLite **缓存**）。**SQLite 永远先做缓存，不当 canonical。**

## 收藏清单

| 收藏 | 主表 | 条数 | 索引页 |
|------|------|------|--------|
| _（空）_ | | | |
