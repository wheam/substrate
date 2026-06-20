# CONSTITUTION — minimal 示例实例

> 本示例遵循 Substrate 引擎默认宪法（完整版见引擎 `template/governance/CONSTITUTION.md`）。这里只列要点。

## 不变量（agent 每次操作必守）

1. 先 `git pull`；完成后 `git commit` + `git push`；操作后列出改了哪些文件。
2. 写前勘察、绝不重复建；相关内容并入已有页。
3. 文件名全小写、连字符、无空格。
4. 每页有 YAML frontmatter（至少 `title / created / updated / type`）；改页 bump `updated`。
5. 每页 `[[wikilinks]]` ≥ 2，并补反向链接。
6. **两级索引同步（硬规则）**：增/改文件必须更新所在 zone README 的文件级索引。
7. 矛盾不静默覆盖，标 `contested: true` 并提请复核。
8. 写入走 skill；密钥/敏感原文/大二进制 = Forbidden，永不进库。

## 新增类型 procedure

要开新 zone：判定够不够 zone → 定最小 schema → 在 `zones.md` 注册 → 建目录 + zone README（含 Agent Packet）+ 接入根 README → 接维护 skill + 跑 doctor。
