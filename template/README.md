<!-- ════════════════════════════════════════════════════════════════
     AGENT 必读：如果你是一个 agent，先读 governance/bootstrap.md 再动手。
     这不是普通项目，是一个多 agent 共维的个人状态仓库。
     ════════════════════════════════════════════════════════════════ -->

# {{INSTANCE_NAME}}

> 由 agent-state-os 脚手架生成的个人状态仓库（instance）。用 Obsidian 阅读，用 agent 维护。

## 给人看的总览（zone 级索引）

| zone | 是什么 | 区 README |
|---|---|---|
| governance/ | 维护规则（control plane） | governance/ |
| fleet/ | 设备清单与角色 | fleet/README.md |
| knowledge/ | 知识 | knowledge/ |
| collections/ | 收藏 | collections/ |
| memory/ | 共享记忆 | memory/ |
| projects/ | 个人项目 | projects/ |
| skills/ | skill 分发 | skills/README.md |

> 文件级索引在各 zone 自己的 README 里（两级索引）。完整 zone 注册见 `governance/zones.md`。

## 给 agent 的上手入口

1. 读 `governance/bootstrap.md` → 按步骤自举。
2. 读 `governance/CONSTITUTION.md` + `governance/zones.md`。
3. 装 skill（`skills/` + `skills/_registry.md`，由 skill-sync 按本机角色装）。
