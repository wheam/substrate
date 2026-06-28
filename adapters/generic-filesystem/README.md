# generic-filesystem — 兜底适配器

把引擎抽象动作落到**纯文件系统**：不假设任何 agent runtime 存在，所有路径可配置。
当本机跑的 agent 不是已有 adapter 覆盖的产品，或你只想用 `grep` / 编辑器 / RAG 直接消费仓库时用它。

> 声明在 `adapter.yaml`（顶部可解析 YAML，python3 标准库可读，不假设 PyYAML）。

## 三问回答

- **skill 装到哪**：调用方给的目录（`SUBSTRATE_SKILL_DIR` 环境变量，未设则 `./.substrate/skills`）。每个 skill = 一个含 `SKILL.md` 的目录，与引擎 `skills/` 同构。
- **怎么探测 runtime/角色**：兜底**不嗅探**，靠显式配置——设了 `SUBSTRATE_SKILL_DIR` 或 `fleet/` 里本机 `runtimes` 含 `generic-filesystem` 即视为可用；角色读 `fleet/` 的 `role`。
- **本地清单存哪**：`SUBSTRATE_SKILL_DIR/installed-skills.json`，**不入库**（`template/.gitignore` 已忽略）。

## 装 skill

```sh
export SUBSTRATE_SKILL_DIR=~/agent-skills            # 你的目标目录
python3 <substrate-sync>/sync.py \
  --src <instance>/skills --target "$SUBSTRATE_SKILL_DIR" --runtime generic-filesystem
# 默认 dry-run（只打计划）；确认后加 --apply
```

`sync.py` 只装 `target_runtimes` 含 `generic-filesystem`（或 `all`）的 skill，并把本地清单写进 `--target`。

## 常驻上下文注入（runtime_context）——默认关

兜底 adapter 在 `adapter.yaml` 里声明了 `runtime_context` 块，但**默认 `default_on: false`**：兜底不替不知名 agent 擅自往它的上下文里塞东西。若你的 agent 能「加载某个文件进上下文/系统提示」，可显式开启,让它每次开工自动带上库摘要（关于主人记忆 + 各区速览 + 意图→skill 路由表 + 房规）：

```sh
export SUBSTRATE_CONTEXT_FILE=~/agent-context/substrate.md   # 你的 agent 会加载的文件
python3 <instance>/skills/substrate-runtime-context/wire-context.py \
  --instance <instance> --runtime generic-filesystem --apply
# 默认关：不传时只打印「默认关」不写文件。注入点（怎么让 agent 读该文件）由你的 agent 决定。
```

派生真实 runtime 的 adapter 时，把 `default_on` 设 true、`digest_file` 指到该 runtime 每次会加载的文件即可（hermes adapter 即如此——见 `../hermes/`）。

## 派生一个真实 runtime 的 adapter

复制本目录到 `adapters/<runtime>/`，把 `runtime` 改名、`target` 换成该 runtime 的固定 skill 目录、`detect.method` 换成探测可执行体（见 `claude-code/`）。
