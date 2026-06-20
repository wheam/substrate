# claude-code — Claude Code 适配器

把引擎抽象动作落到 Claude Code：skill 装进 `~/.claude/skills/`，CC 即自动发现并调用（BUILD-PLAN §6.2）。

> 声明在 `adapter.yaml`（顶部可解析 YAML，python3 标准库可读，不假设 PyYAML）。

## 三问回答

- **skill 装到哪**：`~/.claude/skills/`（可用 `CLAUDE_SKILL_DIR` 覆盖，便于测试）。每个 skill = 一个含 `SKILL.md` 的目录。多 runtime skill 取 `SKILL.claude-code.md` 变体（`sync.py` 落地为 `SKILL.md`）。
- **怎么探测 runtime/角色**：PATH 里有 `claude` 可执行体、或 `~/.claude/` 存在 → 视为本 runtime 可用；角色读 `fleet/` 里本机 `role`。
- **本地清单存哪**：`~/.claude/skills/installed-skills.json`，**不入库**（`template/.gitignore` 已忽略）。

## 装 skill（含首次种子）

```sh
# 1) 首次种子（解决「要 sync 先得有 sync」）：先把 bootstrap + sync 放进 skill 目录
mkdir -p ~/.claude/skills
cp -R <instance>/skills/substrate-bootstrap <instance>/skills/substrate-sync ~/.claude/skills/

# 2) 自助跑 sync 装齐其余（默认 dry-run；确认后加 --apply）
python3 ~/.claude/skills/substrate-sync/sync.py \
  --src <instance>/skills --target ~/.claude/skills --runtime claude-code
```

`sync.py` 只装 `target_runtimes` 含 `claude-code`（或 `all`）且符合本机角色的 skill，并把本地清单写进 `--target`。

> 谁来跑：有管家的机器由管家统一装到各 runtime，CC 不用自己动；**纯 CC 机器**直接如上自助。
