---
title: 工具收藏索引
created: 2026-06-21
updated: 2026-06-21
type: collection
tags: [tools, cli, index]
sources: [示例数据]
---

# 工具收藏索引

> **Agent Packet**
> - zone: collections / tools
> - 维护 skill: `substrate-collections`
> - canonical: `data.csv`（行式主表，单一事实源）
> - 写前查: `data.csv` 里是否已有该 `id`（去重）
> - 写后更新: ① 追加/改 `data.csv`；② 更新 `by-category/` 分片；③ 同步本页条数
> - doctor 检查: 每行有稳定 id；分片条数 = 主表条数；frontmatter 合规

关联：[[markdown]]、[[git]]

## 结构

- **主表**：`data.csv`（当前 **4** 条）——注意用代码路径引用，不用 `[[wikilink]]`（Obsidian 链不到 `.csv`）。
- **分片**：[[cli]]（按类别 `cli` 的人读列表）。

## 查询

按 `category` / `name` 筛主表；要人读列表看对应分片页。
