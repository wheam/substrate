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

## 常驻上下文注入（substrate-runtime-context，对话型助理推荐）

让 Hermes **每个 session 开工自动把库的关键上下文灌进自己**（关于主人的记忆 + 各区速览 +
意图→skill 路由表 + 房规），解决「意图触发飘 / 记忆不进 agent / 不主动用库」。两步：

1. **保持一份最新小抄**（走**通用** `wire-context.py`——落地路径从本 adapter 的 `runtime_context.digest_file` 读，核心不硬编码 `~/.hermes`）：
   ```sh
   cd <instance> && git pull --ff-only -q 2>/dev/null
   python3 skills/substrate-runtime-context/wire-context.py \
       --instance . --runtime hermes --adapters adapters --apply
   # 读本 adapter 的 runtime_context（default_on: true）→ 生成小抄 → 刷新到 digest_file。
   # 测试/多实例可用 HERMES_SUBSTRATE_CONTEXT 覆盖落地路径。
   ```
2. **Hermes 自动加载它**——无需你做任何事（见下「注入点」）。

> ✅ **注入点已在真机验证（2026-06-27，源码 `agent/prompt_builder.py` `build_context_files_prompt`）**：
> Hermes 有原生 **context-file** 机制——网关进程 **cwd = `~/.hermes`**，**每条消息**自动加载该目录下的
> **`.hermes.md`**（优先级最高），加载前做 prompt-injection 安全扫描，每源上限 **20000 字符**。
> 所以把小抄写进 `~/.hermes/.hermes.md` 就被注入:**不用改 `config.yaml`、不用重启、逐条消息生效**。
> （`adapter.yaml` 的 `digest_file` 已指向 `~/.hermes/.hermes.md`。SOUL.md 是独立人设槽位，故意不碰。）

**于是「接线」坍缩成一件事:保持 `~/.hermes/.hermes.md` 刷新。** 因为没有 per-message 的 shell hook，用定时刷新:

- **定时刷新（推荐）**：launchd/cron 或 Hermes 内置 cron 每 N 分钟跑第 1 步（`git pull` + `wire-context.py --apply`）。文件一更新，下条消息 Hermes 即读到最新。
- **能跑 shell 的 agent**：也可在它自己的 session-start 例程里顺手跑第 1 步。

**默认开关**：本注入**默认给 Hermes 开**；claude-code / codex 默认**不**接（各有原生记忆、写代码不需要，整张小抄是噪音）。
**只灌一部分**：若要给写代码型 runtime 选择性开、又不想灌入个人记忆，裁掉小抄的「## 关于主人（记忆）」整段，只留各区速览 + 路由表 + 房规。
