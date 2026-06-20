# adapters — 可插拔 runtime 适配器

把引擎里抽象的动作（"装这个 skill"、"读上手协议"、"写本地清单"）落到具体 runtime 的真实路径与机制。
这是引擎**不绑死 Hermes**、能支持任意 agent 的关键。

每个 adapter 至少回答：
- skill 装到哪个目录、用什么格式（如 Claude Code `~/.claude/skills/`、Hermes `~/.hermes/skills/`、Codex 的 skill 路径/`AGENTS.md`）；
- 本机角色与可用 runtime 怎么探测；
- 本地安装清单存哪。

每个 adapter 是**声明式**的 `adapter.yaml` + `README.md`（不是代码）。`kind` 分两类：

| adapter | kind | 目标 |
|---|---|---|
| `claude-code/` | skill-runtime | Claude Code（`~/.claude/skills`，已做实） |
| `generic-filesystem/` | skill-runtime | 兜底：纯文件系统，路径可配 |
| `codex/` | skill-runtime | Codex（声明，未在真机验证） |
| `hermes/` | skill-runtime | Nous Research Hermes（声明，未在真机验证） |
| `obsidian/` | **view-layer** | Obsidian——**不是 skill runtime**，只放 vault 视图设置（排除目录 / 每设备布局），不装 skill |

> **当前为声明式规范**：`substrate-sync` 暂未自动读取 adapter（`--target` 由调用方传入）；`adapter.yaml` 的 `variant_suffix` 等字段须与 `sync.py` 的 `SKILL.<runtime>.md` 约定**手工保持一致**。让 sync 自动读 adapter 取 target 是后续小项（见 BUILD-PLAN §15 P4）。
> 接口未定稿：先在真实多 runtime 上跑通，接口自然浮现，再抽象稳定 adapter API（必要时加 `schemas/adapter.schema.yaml`）。
