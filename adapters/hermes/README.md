# hermes — Nous Research Hermes 适配器（最小但真实）

把引擎抽象动作落到 Hermes：skill 装进 `~/.hermes/skills/`。

> 声明在 `adapter.yaml`。**接口未定稿**（见 `../README.md`）：路径为占位约定，待真实 Hermes 机验证后固化；未验证前可退回 `generic-filesystem`。Substrate 的目标之一就是「不绑死 Hermes」——本 adapter 让它与 claude-code / codex 平级接入。

## 三问回答

- **skill 装到哪**：`~/.hermes/skills/`（可用 `HERMES_SKILL_DIR` 覆盖）。每个 skill = 一个含 `SKILL.md` 的目录；变体取 `SKILL.hermes.md`。
- **怎么探测 runtime/角色**：PATH 里有 `hermes`、或 `~/.hermes/` 存在 → 可用；角色读 `fleet/` 里本机 `role`。
- **本地清单存哪**：`~/.hermes/skills/installed-skills.json`，**不入库**（`template/.gitignore` 已忽略）。

## 装 skill

```sh
python3 <substrate-sync>/sync.py \
  --src <instance>/skills --target ~/.hermes/skills --runtime hermes
# 默认 dry-run；确认后加 --apply
```
