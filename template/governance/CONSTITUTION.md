# CONSTITUTION — 本实例的全局不变量

> **这是本仓库的唯一权威规则源。** 所有维护 skill 都引用这里；改规则只改这一处。
> 规则**烘焙进 skill**——skill 即「可执行的宪法」，agent 照 skill 做即守规矩，不必每次重读本文件。
> 原则：**少而硬**。只放真正全局、不可破的不变量；具体分区规则在 `zones.md`，准入判定在 `admission.md`。

## 不变量（agent 每次操作必守）

1. **先同步，后改，再推送**：写前 `git pull`；完成后 `git commit`（说清改了什么）+ `git push`；操作后向所有者列出本次创建/修改的所有文件。
2. **写前勘察，绝不重复建**：动手前读相关 zone README 的文件级索引 + 用 grep/glob 搜关键词。相关内容**合并进已有页**，不新建重复页。
3. **命名规范**：文件名全小写、连字符分隔、无空格（如 `some-topic.md`）。
4. **frontmatter 必备**：每个内容页开头有 YAML frontmatter，字段以所在 zone 的 schema 为准（至少 `title / created / updated / type`）。改页时 bump `updated`。
5. **互链（建议，非强制）**：每页**宜**用 `[[wikilinks]]` 链到 ≥2 个相关页，并检查被链页是否需要反向链接——保持知识图连通是好习惯。但这是**建议**：`substrate-doctor` 只提醒（WARN）不报错、不拦路。想收严成硬规则可自行调 doctor。
6. **两级索引同步（硬规则）**：每次新增/修改文件，**必须**同步更新所在 zone README 的文件级索引；新增 zone 时接入根 README 的 zone 级索引。**禁止把全库塞进单点巨表**——索引分两级（见 `concepts.md`「两级索引」）。
7. **矛盾不静默覆盖**：新信息与旧内容冲突时，保留两方 + 日期 + 来源，frontmatter 标 `contested: true`，提请所有者复核。
8. **写入走 skill**：正式状态的写入应经维护 skill 完成（预防漂移）。协议失效时，结果应是「可修复的漂移」，而非「污染正式状态」。
9. **准入红线**：密钥 / 凭据 / 敏感原文 / 大二进制 = **Forbidden，永不进库**。其余按 `admission.md` 四问四去向判定。

## 新增类型 procedure（要开一个新 zone 时走这 5 步）

> 先用尺量：**有独立 schema + 独立维护行为 + 独立访问模式** → 才开新顶层 zone；否则是已有 zone 的一页/一行。

1. **判定**：确认它够 zone，而不只是已有 zone 的一页。（不够就并入已有 zone，到此为止。）
2. **定 schema**：为这类内容定义最小字段集契约（在该 zone 的 README 里声明字段，或记一个 schema 版本名）。字段从最小起步，需要再长。
3. **注册**：在 `zones.md` 顶部 YAML 块加一条，字段见 Substrate 引擎 `schemas/zone.schema.yaml`（`id / path / schema / maintainer_skill / readers / writers`，按需加 `disposition / privacy / graduation`）。
4. **建区**：建目录 + 写 zone README（顶部含 **Agent Packet**：维护 skill / canonical 在哪 / 写前查什么 / 写后更新什么 / doctor 检查项）；接入根 README 的 zone 级索引。
5. **接维护**：指定或扩展 `maintainer_skill`；跑 `substrate-doctor` 确认无断链/孤儿/索引漂移。

## 引用（均在本实例 `governance/` 内）

- 分区注册表 → `zones.md`
- 准入规则（四问 / 四去向 / 去重 / 风险分级） → `admission.md`
- 新 agent 上手 → `bootstrap.md`
- 本实例设计逻辑 → `architecture.md`

> schema 契约与术语定义由 **Substrate 引擎**持有（`schemas/`、`docs/concepts.md`），随维护 skill 一起分发；本实例的 `zones.md` 只记 schema 的**版本名**（如 `collection-zone-v1`），不内嵌契约本体。
