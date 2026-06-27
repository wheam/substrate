# adapters — 可插拔 runtime 适配器

把引擎里抽象的动作（"装这个 skill"、"读上手协议"、"写本地清单"）落到具体 runtime 的真实路径与机制。
这是引擎**不绑死 Hermes**、能支持任意 agent 的关键。

每个 adapter 至少回答：
- skill 装到哪个目录、用什么格式（如 Claude Code `~/.claude/skills/`、Hermes `~/.hermes/skills/`、Codex 的 skill 路径/`AGENTS.md`）；
- 本机角色与可用 runtime 怎么探测；
- 本地安装清单存哪。

可选回答（**常驻上下文注入**，`substrate-runtime-context` 消费）：
- **`runtime_context:`** —— 声明本 runtime 要不要、以及怎么接「常驻小抄」注入。这是引擎做到
  **「越自动越好、又不绑死任何 agent」** 的关键：生成器（`render-context.py`）完全中立，**唯一**
  因 runtime 而异的「怎么把小抄喂给这个 agent」声明在这里，`wire-context.py` 通用地照着接、核心不认 runtime 名。
  | 字段 | 含义 |
  |---|---|
  | `default_on` | `true`=该 runtime 默认接注入（对话型助理如 hermes/openclaw）；缺省/`false`=默认关（写代码型如 claude-code/codex 不声明即天然落到关） |
  | `digest_file` | 小抄落地的本地文件路径（不入库；`~`/`${ENV}` 可展开） |
  | `digest_file_env_override` | 覆盖上面路径的环境变量名（测试/多实例用） |
  | `inject_via` | 一次性接线指令：怎么让该 runtime 启动时加载 `digest_file`（注入点，因 runtime 而异） |
  | `refresh` | 每会话怎么刷新小抄（runtime 自带 session-start hook，或 launchd/cron） |
  > 给一个**新 agent**（openclaw…）上这套 = 往它的 adapter 加一个 `runtime_context` 块 + 查一次它的注入点；**核心代码零改动**。没有专属 adapter 的 agent 走 `generic-filesystem` 的 `runtime_context` 兜底。

每个 adapter 是**声明式**的 `adapter.yaml` + `README.md`（不是代码）。`kind` 分两类：

| adapter | kind | 目标 |
|---|---|---|
| `claude-code/` | skill-runtime | Claude Code（`~/.claude/skills`，已做实） |
| `generic-filesystem/` | skill-runtime | 兜底：纯文件系统，路径可配 |
| `codex/` | skill-runtime | Codex（声明，未在真机验证） |
| `hermes/` | skill-runtime | Nous Research Hermes（声明，未在真机验证） |
| `obsidian/` | **view-layer** | Obsidian——**不是 skill runtime**，只放 vault 视图设置（排除目录 / 每设备布局），不装 skill |

> **声明式规范 + 已被消费**：`substrate-sync` 省略 `--target` 时**会读 `adapters/<runtime>/adapter.yaml` 推断安装目录**（认 `skill_install.target`、`target_env_override`、`target_fallback`；`kind: view-layer` 的 adapter 会被拒绝）。`variant_suffix` 等字段仍须与 `sync.py` 的 `SKILL.<runtime>.md` 约定**手工保持一致**。
> 接口未定稿：先在真实多 runtime 上跑通，接口自然浮现，再抽象稳定 adapter API（必要时加 `schemas/adapter.schema.yaml`）。
