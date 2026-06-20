<!-- ════════════════════════════════════════════════════════════════
     AGENT 必读：如果你是一个 agent，先读 governance/bootstrap.md 再动手。
     这不是普通项目，是一个多 agent 共维的个人状态仓库。
     ════════════════════════════════════════════════════════════════ -->

# minimal — Substrate 最小示例实例

> 由 Substrate 脚手架生成的个人状态仓库（instance）示例。**内容是中立假数据**，仅用于演示机制 + 当 `substrate-doctor` 的靶子。
> 用 Obsidian 阅读，用 agent 维护。

## 给人看的总览（zone 级索引）

| zone | 是什么 | 区 README |
|---|---|---|
| governance/ | 维护规则（control plane） | governance/CONSTITUTION.md |
| knowledge/ | 知识页 | knowledge/README.md |
| collections/ | 收藏 | collections/tools/tools.md |

> 文件级索引在各 zone 自己的 README 里（两级索引）。完整 zone 注册见 `governance/zones.md`。

## 给 agent 的上手入口

1. 读 `governance/bootstrap.md`（本示例从略，见引擎 `template/governance/bootstrap.md`）→ 按步骤自举。
2. 读 `governance/CONSTITUTION.md` + `governance/zones.md`。
3. 要写某个 zone 前，先读该 zone README 顶部的 **Agent Packet**。

## 这个示例演示了什么

- **两级索引**：本 README 只做 zone 级路由；`knowledge/README.md`、`collections/tools/tools.md` 各管本区文件级索引。
- **Agent Packet**：每个 zone README 顶部的固定字段块。
- **互链知识页**：`knowledge/` 三页互相 `[[wikilink]]`（无断链、无孤儿）。
- **collections**：`collections/tools/data.csv`（行式 canonical 主表）+ `by-category/` 人读分片 + 索引页。
