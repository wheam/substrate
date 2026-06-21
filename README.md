# Substrate

**A git-native, agent-operable "shared state layer" for your personal AI agent fleet.** Knowledge, memory, skills, lists, rules, and an audit trail — in one versionable, migratable system that no platform can lock away. Multiple agents across multiple machines can safely co-maintain it.

> **个人 AI agent 舰队的「共享状态层」——git 原生、可被 agent 操作。** 知识、记忆、技能、清单、规则、审计，都在一个可版本化、可迁移、不被任何平台锁死的系统里；多个 agent、多台机器可以安全地共同维护它。

This repo is the **engine**: a neutral, open template + mechanism with **zero personal content**. You build your own *private* **instance** on top of it — your stuff lives in a separate repo that the engine never depends on.

> 这个仓库是**引擎**:中立、开源的模板 + 机制,**不含任何个人内容**。你在它之上搭自己的**私有实例**——你的内容放在另一个仓库里,引擎从不依赖它。

---

## What it is / isn't

It's the **engine + template + reference skills + adapters + migrations** to stand up your own "personal state repo that multiple agents co-maintain." It turns "how to maintain a repo many agents/machines write to over time" into reusable mechanism: governance, zones, admission control, skill distribution, shared memory, anti-rot health checks, safe upgrades.

> 它是让你搭起「多 agent 共维的个人状态仓库」的**引擎 + 模板 + 参考 skill + adapter + 迁移**。它把"怎么维护一个被多 agent/多机器长期共写的仓库"沉淀成可复用机制:治理、分区、准入、skill 分发、记忆共享、防退化体检、安全升级。

It is **not** another Obsidian or RAG. The product is a **shared state layer** you fully own and can migrate — not a note-taking app.

> 它**不是**又一个 Obsidian 或 RAG。它卖的是你**完全拥有、可迁移**的**共享状态层**,不是笔记软件。

---

## Quick start

You'll end up with two git repos: the **engine** (this one, public, mechanism only) and your **instance** (private, holds your knowledge / memory / skills / lists).

> 你会有两个 git 仓库:**引擎**(这个,公开,只含机制)+ **你的实例**(私有,放你的知识/记忆/技能/清单)。

### Option A — let your agent set it up (recommended)

Hand the engine URL + the prompt below to any agent that can run shell commands (Claude Code, Codex, Hermes, …). It does the whole setup for you.

> ### 方式 A —— 让你的 agent 帮你搭(推荐)
> 把引擎地址 + 下面这段 prompt 丢给任何能跑 shell 的 agent(Claude Code、Codex、Hermes…),它会替你把整套搭好。

```text
I want to set up a personal knowledge base using the Substrate engine:
https://github.com/wheam/substrate

Please do it for me:
1. Clone the engine to a temp dir and read its README.
2. Ask me for: where to put my instance, a short instance name, my GitHub username.
3. Scaffold my private instance: run ./init-instance.sh <dir> <name>, then
   `git init && git add -A && git commit -m "init"` inside it.
4. Install the maintenance skills into YOUR runtime:
   python3 <instance>/skills/substrate-sync/sync.py --src <instance>/skills --runtime <your-runtime> --apply
5. Run substrate-doctor on the instance and confirm 0 errors.
6. Tell me how to push the instance to a PRIVATE GitHub repo, and give me a few
   example phrases to start using it.

Never put any of my personal content into the public engine repo.
```

### Option B — manual (4 steps)

> ### 方式 B —— 手动 4 步

**Prereqs / 前置**: `git`, `python3` (standard library only — **no pip installs**), and an agent runtime that can read skills.

```sh
# 1) Get the engine (or fork it to your account first)
git clone https://github.com/wheam/substrate.git && cd substrate

# 2) Scaffold your private instance (self-contained: template + vendored skills + adapters)
./init-instance.sh ~/my-cortex my-instance
cd ~/my-cortex && git init && git add -A && git commit -m "init my substrate instance"
#   Then create a PRIVATE GitHub repo and push it (your content stays private)

# 3) Install the maintenance skills into your runtime
python3 ~/my-cortex/skills/substrate-sync/sync.py \
        --src ~/my-cortex/skills --runtime claude-code --apply
#   Swap --runtime for codex / hermes / … (see adapters/)

# 4) Onboard your agent: tell it "get set up on my personal repo"
#    → triggers substrate-bootstrap (reads the constitution + zones, sets identity, self-checks)
```

That's it — you now have a multi-agent, git-native, migratable personal state layer. On a new machine or agent, just `git clone` your instance and re-run step 3.

> 完工——你就有了一个多 agent 共维、git 原生、可迁移的个人状态层。换机器/换 agent,只要 `git clone` 你的实例 + 重跑第 3 步即可。

---

## Daily use — talk to your agent

Once installed, use plain language; your agent triggers the right skill.

> ## 日常使用 —— 和你的 agent 对话
> 装好后用自然语言,agent 会触发对应 skill。

| You say / 你说 | Skill |
|---|---|
| "note this / save to my knowledge base" · 「记一下 / 存进知识库」 | `substrate-curator` |
| "save this restaurant / add to my book list" · 「收藏这家餐厅 / 加到书单」 | `substrate-collections` |
| "remember that I… / my preference is…" · 「记住我… / 我的偏好是…」 | `substrate-memory` |
| "add a todo / what's left" · 「加个待办 / 还有啥没做」 | `substrate-todo` |
| "should I save this / where does it go" · 「这个要不要存 / 存哪」 | `substrate-intake` |
| "import these notes / this vault" · 「把这些笔记导进库」 | `substrate-import` |
| "health-check my repo" · 「体检一下库」 | `substrate-doctor` |
| "install / align skills" · 「装 / 对齐 skill」 | `substrate-sync` |

---

## Keeping machines in sync

The repo is co-maintained, so each machine's copy can fall behind. At the start of a session, have your agent run the self-check: `git pull` → `substrate-sync --check` → if behind, `--apply` → `substrate-doctor`. `--check` does a best-effort `git fetch` and flags when you're behind the remote, so a silently-failed pull can't masquerade as "up to date."

> ## 多机/多 agent 保持一致
> 仓库是共维的,每台机器的副本都可能落后。每次开工让 agent 跑自检:`git pull` → `substrate-sync --check` → 落后则 `--apply` → `substrate-doctor`。`--check` 会顺带 `git fetch` 比对远程、**本地落后也能发现**,所以静默失败的 pull 不会冒充"已最新"。

To fully automate it, wire your runtime's own session-start hook to run that routine (see `template/governance/bootstrap.md`).

> 想全自动,就给你的 runtime 接一个原生的会话启动钩子跑这套(见 `template/governance/bootstrap.md`)。

---

## Upgrading (no data loss)

When the engine ships a new version, in **your instance**: refresh the vendored skills, then let your agent run the migration.

> ## 升级(不丢数据)
> 引擎发新版后,在**你的实例**里:先刷新 vendored 的维护 skill,再让 agent 跑迁移。

```sh
/path/to/substrate/init-instance.sh --refresh ~/my-cortex   # refresh vendored skills
#   then: tell your agent "upgrade my repo" → triggers substrate-migrate
```

Migrations run like database migrations — ordered, idempotent, verifiable, reversible — and **never lose data** (git-tag snapshot + before/after doctor checks; multi-machine runs only on the device flagged `migration_leader`).

> 迁移当**数据库迁移**做:有序/幂等/可验证/可回滚,**绝不丢数据**(git tag 快照 + doctor 前后校验;多机只在标了 `migration_leader` 的机器上跑)。

---

## The core idea: Engine / Instance separation

This split is what lets the engine be open while your content stays private.

> ## 核心:Engine / Instance 分离
> 正是这个拆分,让引擎可以开源、而你的内容保持私有。

| | Engine (this repo, public) | Instance (your private repo) |
|---|---|---|
| Holds / 内容 | mechanism, template, schemas, reference skills, adapters, migrations | knowledge, collections, memory, todos, projects, fleet, private skills |
| Constraint / 约束 | must not depend on any user's incidental facts | your stuff, layered on top of the engine |

The engine decides *how* to maintain; your instance decides *what* to maintain. They are two independent git repos.

> 引擎决定"怎么维护",实例决定"维护什么"。两者是两个独立的 git 仓库。

---

## Learn more / Contributing

- **Concepts & design**: `docs/concepts.md`, `docs/architecture.md`
- **Full design + roadmap**: `docs/BUILD-PLAN.md`
- **Hacking on the engine itself**: `CONTRIBUTING.md` (red lines, contract-first, skills-first, self-checks)
- **Run the tests**: `sh tests/run-tests.sh` (zero-dependency)

> ## 了解更多 / 参与开发
> 概念与设计见 `docs/`;想给引擎本身写代码看 `CONTRIBUTING.md`;测试 `sh tests/run-tests.sh`(零依赖)。

## License

MIT — see `LICENSE`.
