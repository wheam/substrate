---
title: Git
created: 2026-06-21
updated: 2026-06-21
type: concept
tags: [vcs, storage]
sources: [示例数据]
---

# Git

分布式版本控制系统。Substrate 把它当个人状态仓库的存储与同步底座：全历史可回溯、可多机协作、可打 tag 做迁移快照。

## 要点

- 每次维护操作前 `git pull`、后 `git commit + push`（见宪法不变量 1）。
- 迁移用 `git tag` 做零成本回滚点（`pre-migrate-<from>`）。
- 配合 [[markdown]] + [[wikilinks]]：内容是纯文本，git diff 清晰可审计。
