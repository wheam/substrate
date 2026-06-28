# memory / about-owner — 关于主人的共享记忆

> **Agent Packet**
> - zone: memory
> - 维护 skill: `substrate-memory`
> - canonical: 本目录下的 `*.md`（跨 agent 共享的「关于主人」记忆）
> - 写前查: 是否已有同一事实的记忆（去重/更新而非新建）
> - 写后更新: 本 README 索引；冲突标 `contested`
> - doctor 检查: 缺 frontmatter / 断链；敏感信息是否误入（应走 admission 的 forbidden 判定）
>
> 🔒 `privacy: sensitive`。owner 可在下方把 `readers/writers` 收窄到特定 runtime。

## 命名约定（引擎中立）

- **`about-owner/` 是稳定的通用槽位名**——「主人是谁」（名字/偏好）写在**内容**里（`owner: <你的名字>`），**不进 folder 名**。这样 skill 不硬编码任何人名。
- 这里放跨 agent 都该知道的关于主人的稳定事实/偏好；一次性、临时、或仅本机相关的归 local-only（见 `../../governance/admission.md`）。

## 访问收窄（可选）

默认 `readers/writers: [all]`。若某些记忆只该给特定 runtime 看，在 `../../governance/zones.md` 把 memory 区的 readers/writers 改为具体 runtime（如 `[claude-code]`）。

## 形态：核心摘要 + 分类页（按需读）

为了让常驻上下文（`substrate-runtime-context`）每条消息只带「核心」而不随记忆膨胀：

- **`_core.md`**（结构页，下划线前缀）= **核心摘要**：跨场景永远该知道的身份 + 最关键偏好，由 `substrate-memory` 蒸馏维护，**≤ 3000 字符**（doctor 超量告警）。它**整段**进常驻小抄。
- **分类页 `*.md`**（如 `communication-preferences.md`）= 细节。**正文不进小抄**，只有 frontmatter 的 `summary`（一句话）进「记忆目录」；agent 需要细节时才用 `substrate-memory` 现读本页。

## frontmatter

```yaml
---
title: 记忆标题
type: memory
owner: <你的名字>
created: YYYY-MM-DD
updated: YYYY-MM-DD
summary: 一句话摘要        # 进常驻小抄的「记忆目录」；不写则退回 title
tags: [偏好/事实/...]
sources: [来源]
---
```

## 索引

| 文件 | 摘要 |
|------|------|
| _（空）_ | |
