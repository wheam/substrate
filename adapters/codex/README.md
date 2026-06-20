# codex — Codex 适配器（最小但真实）

把引擎抽象动作落到 Codex：skill 装进 `~/.codex/skills/`，上手协议经仓库根 `AGENTS.md`（CLAUDE.md 的镜像）暴露。

> 声明在 `adapter.yaml`。**接口未定稿**（见 `../README.md`）：路径为占位约定，待真实 Codex 机验证后固化；未验证前可退回 `generic-filesystem`。

## 三问回答

- **skill 装到哪**：`~/.codex/skills/`（可用 `CODEX_SKILL_DIR` 覆盖）。每个 skill = 一个含 `SKILL.md` 的目录；变体取 `SKILL.codex.md`。
- **怎么探测 runtime/角色**：PATH 里有 `codex`、或 `~/.codex/` 存在 → 可用；角色读 `fleet/` 里本机 `role`。
- **本地清单存哪**：`~/.codex/skills/installed-skills.json`，**不入库**（`template/.gitignore` 已忽略）。

## 装 skill

```sh
python3 <substrate-sync>/sync.py \
  --src <instance>/skills --target ~/.codex/skills --runtime codex
# 默认 dry-run；确认后加 --apply
```
