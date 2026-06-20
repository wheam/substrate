---
title: Wikilinks
created: 2026-06-21
updated: 2026-06-21
type: concept
tags: [format, linking]
sources: [示例数据]
---

# Wikilinks

`[[页面名]]` 形式的双向链接语法，让 [[markdown]] 文件之间互相引用，形成知识图谱。Obsidian 原生支持。

## 要点

- 约定即接口：用 `[[name]]` 而非完整路径，工具与 agent 都能解析。
- Substrate 要求每页 ≥2 个 wikilink，并补反向链接——避免孤立页。
- doctor 靠 `grep` 抽取 `[[...]]` 做集合差，检出断链与孤儿。
- 链接图随内容存进 [[git]]，可版本回溯。
