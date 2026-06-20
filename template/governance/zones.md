# zones — 分区注册表

> 顶部是**可解析 YAML 块**：`substrate-doctor` / `substrate-sync` 解析它，不去猜下面的 markdown。
> 每条字段契约见 Substrate 引擎 `schemas/zone.schema.yaml`。字段从最小集起步，需要再长。
> 新增 zone 走 `CONSTITUTION.md` 的「新增类型 procedure」5 步。

```yaml
zones:
  - id: knowledge
    path: knowledge/
    purpose: 互链知识页（分类由本实例自定，如 concept/entity/comparison/insight）
    schema: knowledge-zone-v1
    maintainer_skill: substrate-curator
    readers: [all]
    writers: [all]
    disposition: canonical
    privacy: private

  - id: collections
    path: collections/
    purpose: 通用收藏（行式 canonical 主表 + 人读分片索引）
    schema: collection-zone-v1
    maintainer_skill: substrate-collections
    readers: [all]
    writers: [all]
    disposition: canonical
    privacy: private
    graduation: "rows>2000 → 分片 JSONL；需 join/复杂筛 → 本地 SQLite 缓存（缓存非 canonical）"

  - id: memory
    path: memory/about-owner/
    purpose: 跨 agent 共享的「关于主人」记忆（owner 名/偏好写在内容里，不进 folder 名）
    schema: memory-zone-v1
    maintainer_skill: substrate-memory
    readers: [all]
    writers: [all]
    disposition: canonical
    privacy: sensitive

  - id: projects
    path: projects/
    purpose: 个人非代码项目
    schema: project-zone-v1
    maintainer_skill: substrate-curator
    readers: [all]
    writers: [all]
    disposition: canonical
    privacy: private

  - id: fleet
    path: fleet/
    purpose: 设备清单 + 每台机角色（实例数据）
    schema: fleet-zone-v1
    maintainer_skill: substrate-sync
    readers: [all]
    writers: [all]
    disposition: canonical
    privacy: internal

  - id: skills
    path: skills/
    purpose: skill 分发（自写 + 第三方指针 + 回流隔离区）
    schema: skill-zone-v1
    maintainer_skill: substrate-sync
    readers: [all]
    writers: [all]
    disposition: canonical
    privacy: private

  - id: raw
    path: raw/
    purpose: 原始素材存档（只读：只追加，不修改）
    schema: raw-zone-v1
    maintainer_skill: substrate-curator
    readers: [all]
    writers: [all]
    disposition: reference
    privacy: private
```

---

## 人话说明

- **knowledge/**：本实例的知识页。**怎么分类由你定**——可以像很多 LLM wiki 那样分 `concept / entity / comparison / insight`，也可以另起。引擎只要求：每页带 frontmatter、互链 ≥2、文件级索引在本区 README。
- **collections/**：结构化收藏。行式 canonical 主表（CSV/JSONL）是单一事实源，地区/分类分片页只是人读索引。规模见 `graduation` 字段。
- **memory/about-owner/**：跨 agent 共享记忆。**`about-owner` 是稳定的通用槽位名**，「主人是谁」写在内容里（`owner: <你的名字>`），不进 folder 名。`privacy: sensitive`——owner 可在本区 README 把 `readers/writers` 收窄到特定 runtime。
- **projects/**：个人非代码项目（代码项目用 .gitignore 排除其路径，不进库，见 `.gitignore`）。
- **fleet/**：哪几台机、各自角色（如 `main-dev` / `headless-dev` / `migration_leader`）。引擎只给槽位，**具体机器是你的实例数据**。
- **skills/**：见 `skills/README.md`（三类 skill + 多 runtime 约定 + `_incoming` 回流）。
- **raw/**：原始素材只读归档；更正写进对应知识页，不改原始素材。

> 这是脚手架默认分区，**按需增删**。删一个 zone：从上面 YAML 块移除该条 + 删目录 + 从根 README 去掉其 zone 级索引 + 跑 doctor。
