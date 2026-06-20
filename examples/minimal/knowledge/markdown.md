---
title: Markdown
created: 2026-06-21
updated: 2026-06-21
type: concept
tags: [format, markup]
sources: [示例数据]
---

# Markdown

一种轻量标记语言，用纯文本加少量符号表达标题、列表、链接、代码等结构。可读性高、diff 友好，是 Substrate 数据面的基础格式。

## 要点

- 纯文本：任何编辑器、`grep`、RAG 都能消费，零迁移。
- 常配合 YAML frontmatter 存元数据（见各页开头）。
- 在本库里用 [[wikilinks]] 做页面互联，用 [[git]] 做版本化存储。
