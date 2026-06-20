# adapters — 可插拔 runtime 适配器

把引擎里抽象的动作（"装这个 skill"、"读上手协议"、"写本地清单"）落到具体 runtime 的真实路径与机制。
这是引擎**不绑死 Hermes**、能支持任意 agent 的关键。

每个 adapter 至少回答：
- skill 装到哪个目录、用什么格式（如 Claude Code `~/.claude/skills/`、Hermes `~/.hermes/skills/`、Codex 的 skill 路径/`AGENTS.md`）；
- 本机角色与可用 runtime 怎么探测；
- 本地安装清单存哪。

| adapter | 目标 |
|---|---|
| `claude-code/` | Claude Code |
| `codex/` | Codex |
| `hermes/` | Nous Research Hermes |
| `generic-filesystem/` | 兜底：纯文件系统，无特定 runtime |

> 接口未定稿。先在私有 instance 上把 Hermes + Claude Code + Codex 三者跑通，接口自然浮现，再抽象成稳定 adapter API。
