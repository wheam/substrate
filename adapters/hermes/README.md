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

1. **保持一份最新小抄**（输出落本地文件，不入库）：
   ```sh
   cd <instance> && git pull --ff-only -q 2>/dev/null
   python3 skills/substrate-runtime-context/render-context.py . > ~/.hermes/substrate-context.md
   ```
2. **让 Hermes 启动时把该文件加载进 system prompt / 上下文。**

按 Hermes 能否自己跑 shell 分两条路：

- **A — 自助（默认，Hermes 能跑 shell）**：把第 1 步接进 Hermes 的 session-start / 启动 hook，让它每次开工自己刷新；第 2 步在 config 里配一次。能跑 shell 的 agent 读本节即可自己接。
- **B — 纯聊天网关（不能跑 shell）**：用 launchd/cron 定时跑第 1 步刷新文件；Hermes 只负责第 2 步加载。需一个有 shell 的人/agent 接一次；之后运行时零 shell。

> ⚠️ **注入点待真机确认**：Hermes 具体从哪读 system prompt / 启动 hook（`config.yaml` 哪个字段？启动脚本？）尚未在真实 Hermes 机上 round-trip 验证。先按「`config.yaml` 的 system prompt 加载该文件 + 启动 hook 刷新」落，真机验证后把确切口子写回本节与 `adapter.yaml` 的 `runtime_context`。

**默认开关**：本注入**默认给 Hermes 开**；claude-code / codex 默认**不**接（各有原生记忆、写代码不需要，整张小抄是噪音）。
**只灌一部分**：若要给写代码型 runtime 选择性开、又不想灌入个人记忆，在第 2 步前裁掉小抄的「## 关于主人（记忆）」整段，只留各区速览 + 路由表 + 房规。
