# Substrate

**One private place all your AI assistants share — so every one of them knows who you are and what you've saved.**

> **一个你私有、所有 AI 助手共用的地方——让它们每一个都认识你、都知道你存过什么。**

You probably use several AIs now — Claude on your laptop, a chatbot on your phone, maybe one on a server. Normally each is a stranger: you re-explain yourself every time, and whatever you tell one, the others never learn. Substrate gives them a **shared memory and knowledge base that you own**. Tell any of them *"remember this,"* *"save that restaurant,"* *"note this down"* — and it lands in one private folder that all of them can read and write. Under the hood it's just plain text files in a Git repo: yours forever, movable anywhere, locked into no app.

> 你现在大概在用好几个 AI——电脑上的 Claude、手机上的聊天机器人、也许还有服务器上的。平时它们互不相识:你得对每个重新介绍自己,告诉这个的事那个永远不知道。Substrate 给它们一个**你自己拥有的共享记忆 + 知识库**。对任何一个说*「记住这个」*、*「收藏这家餐厅」*、*「记一下」*,它就落进同一个私有文件夹,所有 AI 都能读写。底层就是 Git 仓库里的纯文本文件:永远是你的、能搬到任何地方、不被任何 app 锁住。

This repo is the reusable **template** (the "engine"). You don't put your data here — you use it to spin up your **own private copy**, where your notes actually live. The rest of this page shows you how.

> 这个仓库是可复用的**模板**(也就是"引擎")。你的数据**不放在这里**——你用它生成一份**自己的私有副本**,笔记存在那份里。下面教你怎么搭。

---

## What you can do with it

- **Tell it once, every AI knows.** "I'm vegetarian," "my job is X," "I prefer Y" — saved once, shared by all your assistants. Stop re-introducing yourself to each new chat.
- **Save the things you'd otherwise lose.** Facts worth keeping, restaurants worth remembering, books to read, running to-dos — just say "save this" and your AI files it, and links it to related notes so you can find it again.
- **It stays tidy on its own.** New notes get auto-linked to related ones; a built-in health check catches broken links and clutter so it doesn't rot into a mess.
- **You own it, fully.** Everything is plain Markdown in your own private Git repo. Back it up, read it by hand, move it to another tool, share parts — no lock-in, no cloud you don't control.

> ## 你能拿它干什么
> - **说一次,所有 AI 都知道。** 「我吃素」「我做的是 X」「我偏好 Y」——存一次,所有助手共享。不用再对每个新对话重新自我介绍。
> - **存下那些本来会丢的东西。** 想留的事实、值得记住的餐厅、想读的书、没做完的待办——说句「存一下」,AI 就帮你归档,还链到相关笔记,方便以后找回。
> - **它自己保持整洁。** 新笔记自动链到相关的;内置体检会抓断链和杂乱,不让它烂成一团。
> - **完全属于你。** 全是你私有 Git 仓库里的纯 Markdown。能备份、能手翻、能搬到别的工具、能选择性分享——不锁定、不依赖你管不到的云。

**It's not** another note-taking app, and not a single chatbot with memory bolted on. It's the layer *underneath*: the place your data lives and that any AI can plug into.

> **它不是**又一个笔记 app,也不是某一个加了记忆的聊天机器人。它是底下那一层:你数据的归属地,任何 AI 都能接进来。

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

Please do it for me, and STOP and tell me if any step fails (don't silently continue):
1. Check prereqs: git + python3 (>=3.8) exist, and git is authenticated to GitHub
   (`gh auth status`, or an SSH key, or an HTTPS token). If auth is missing, stop and
   tell me how to set it up — clone/push will dead-end without it.
2. Clone the engine to a temp dir and read its README.
3. Ask me for: where to put my instance, a short instance name, my GitHub username.
4. Scaffold my private instance: run ./init-instance.sh <dir> <name>, then
   `git init && git add -A && git commit -m "init"` inside it.
5. Install the maintenance skills into YOUR runtime:
   python3 <instance>/skills/substrate-sync/sync.py --src <instance>/skills --runtime <your-runtime> --apply
   Then VERIFY at least one skill was actually installed. If 0 were installed, the
   --runtime value is wrong for your agent — stop and ask me.
6. Run substrate-doctor on the instance; if it reports any ERROR, stop and show me.
6b. (Only if YOUR runtime is a conversational assistant like Hermes — skip for code-focused
   runtimes such as Claude Code / Codex) Wire standing-context injection so you auto-load my
   memory + repo map + an intent→skill router every session, instead of waiting to be asked:
   see adapters/<your-runtime>/README.md (the `substrate-runtime-context` section).
7. Create a PRIVATE GitHub repo, add it as the remote, and `git push -u origin main`.
   VERIFY the push actually succeeded — a local-only instance silently disables all
   multi-machine sync. If you can't push, stop and tell me exactly what to fix (auth).
8. Give me a few example phrases to start using it.

Never put any of my personal content into the public engine repo.
```

### Option B — manual (4 steps)

> ### 方式 B —— 手动 4 步

**Prereqs / 前置**: `git` **authenticated to GitHub** (`gh auth login`, or an SSH key, or an HTTPS token — you'll push your instance to a **private** repo, so set this up first), `python3` ≥ 3.8 (standard library only — **no pip installs**), and an agent runtime that can read skills.

> **前置**：`git`（**先认证到 GitHub**——`gh auth login` / SSH key / HTTPS token，因为下一步要把实例推到**私有**仓库，没认证会卡在 clone/push）、`python3` ≥ 3.8（仅标准库，**无需 pip**）、一个能读 skill 的 agent runtime。

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
#   NOTE: claude-code + generic-filesystem are verified; codex/hermes adapter paths are
#   provisional (declared, not yet round-tripped on real hardware) — after install, verify
#   the skill actually landed where your agent reads skills from.

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

To fully automate it, wire your runtime's own session-start hook to run that routine. A copy-pasteable Claude Code `SessionStart` hook ships in `adapters/claude-code/README.md`; for other runtimes see `template/governance/bootstrap.md`.

> 想全自动,就给你的 runtime 接一个原生的会话启动钩子跑这套。Claude Code 的现成 `SessionStart` hook 模板在 `adapters/claude-code/README.md`;其它 runtime 见 `template/governance/bootstrap.md`。

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
