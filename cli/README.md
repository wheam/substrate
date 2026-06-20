# cli — agent-state（设想，待实现）

无状态薄壳，把抽象操作落到具体仓库 + runtime（通过 `../adapters/`）。

| 命令 | 作用 |
|---|---|
| `agent-state init` | 把 `../template/` 脚手架成一个新 instance 仓库 |
| `agent-state doctor` | 跑 wiki-doctor 增量体检（断链/孤儿/索引漂移/registry 风险） |
| `agent-state sync-skills` | 按本机角色选择性安装/更新 skill，维护本地清单 |
| `agent-state admit` | 审查 `skills/_incoming/`，晋升低风险或转人工 audit |
| `agent-state new-zone <id>` | 按宪法 procedure 新增一个内容类型 |

> 实现语言待定。CLI 不是必需品——所有操作也可由参考 skill 在 agent 内完成；CLI 只是给人/CI 的便捷入口。
