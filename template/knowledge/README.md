# knowledge — 知识页

> **Agent Packet**
> - zone: knowledge
> - 维护 skill: `substrate-curator`
> - canonical: 本目录下的 `*.md`，每页一个主题
> - 写前查: 下方文件级索引 + grep 关键词，**绝不重复建页**（相关内容并入已有页）
> - 写后更新: 下方索引行（文件/摘要/关联）；被链页的反向链接；改页 bump `updated`
> - doctor 检查: 断链 / 孤儿（无入链）/ 缺 frontmatter / 互链 <2 / 索引漂移

## 分类法（本实例自定）

引擎不规定知识怎么分。常见做法是分 `concept / entity / comparison / insight`（可放子目录，也可只靠 frontmatter 的 `type` 区分）。在 `../governance/architecture.md` 写下你的选择。

## frontmatter

```yaml
---
title: 页面标题
created: YYYY-MM-DD
updated: YYYY-MM-DD
type: concept        # 你定义的知识类型
tags: [相关标签]
sources: [来源，如 对话日期/URL]
# contested: true    # 仅当与旧内容冲突、双留待复核时
---
```

## 文件级索引（每次增/改必须同步——CONSTITUTION 不变量 6）

| 文件 | 摘要 | 关联 |
|------|------|------|
| _（空）_ | | |
