---
name: substrate-runtime-context
description: "Generate a bounded 'standing context digest' (owner memory + each zone's Agent Packet + an intent→skill router + house rules) and wire a runtime's session-start hook to inject it — so an agent like Hermes knows who the owner is, what's in the repo, and when to use which skill WITHOUT being told each session. Use when the user says 'my agent doesn't auto-use the knowledge base / doesn't know my memory / should use the repo proactively / set up ambient access'. 中文触发：「让 Hermes 自动用我的库 / 它不知道我的记忆 / 开工就懂我的库 / 接常驻上下文 / 主动用知识库」。"
target_runtimes: [all]
risk_level: medium
capabilities: [shell]
reason: 生成常驻上下文小抄（读 about-owner + 各区 Agent Packet + 派生路由表）并把注入 hook 接进 runtime（读文件、跑 git、改 runtime 启动配置）
---

# substrate-runtime-context — runtime 常驻接入层

让一个 runtime（Hermes / openclaw…）**每个 session 开工时自动把库的关键上下文灌进自己**，从而解决三件事：
① 意图识别飘（说「待办」不触发 todo）→ 路由表；② 库里记忆不进 agent → 开工即读 about-owner；
③ 不主动用库 → 各区速览 + 房规。核心是一张**定量小抄**：只拼摘要，永不通读全库。

> 「调用某 skill」= 读它的 `SKILL.md` 并执行。本 skill 自带两个零依赖脚本：
> - **`render-context.py`** —— 纯生成器，产出小抄到 stdout，**完全 runtime 中立**。
> - **`wire-context.py`** —— 通用「按 adapter 接注入」：读 `adapters/<runtime>/adapter.yaml` 的 `runtime_context` 块决定开/关、生成并刷新小抄到声明的落地文件。**核心不认任何 runtime 名**——hermes / openclaw / 将来任意 agent 都走同一通路，给它写个 adapter 块即可。

## 默认开关（按决策）

区分两件事——**装 skill**（中立、到处装）vs **接注入 hook**（按 runtime 选择）：

- skill 本身 `target_runtimes: [all]`：生成器是中立的，装到哪个 runtime 都行、闲着不花上下文。
- **注入 hook 默认只给 `hermes`（及 openclaw 等对话型助理）接**——它们是「生活助理」，常驻记忆才是重点。
- **claude-code / codex 默认不接 hook**：它们主要写代码、且各自有原生记忆；整张小抄对写代码是噪音。所以即便 skill 装着，**对 cc/codex 会话零影响**（没接 hook = 不灌）。要用再单独接（见下「只灌一部分」）。

## 小抄长什么样（render-context.py 的输出）

```
# Substrate 常驻上下文（自动生成，勿手改）
## 关于主人（记忆）        ← memory/about-owner/*.md 正文（剥 frontmatter）
## 库里有什么（各区速览）   ← 每个 zone README 顶部的 Agent Packet
## 何时用哪个 skill（路由表）← 从已装 skill 的 description 自动派生
## 房规                     ← house-rules.md（先提议后写等常驻规矩）
```

- **定量**：体积不随库变大而变大；超 `SUBSTRATE_CONTEXT_MAX_CHARS`（默认 12000 字符 ≈ 3–4k token）只在 stderr 告警，不截断、不失败。
- **自维护**：库内容/装的 skill 一变，下次重跑即新——**永不手动维护小抄**。

```sh
python3 <本 skill 目录>/render-context.py <实例根>                       # 只打印小抄（中立）
python3 <本 skill 目录>/wire-context.py --instance <实例根> --runtime <名> --apply
#   按 adapter 生成并刷新到落地文件。--adapters 默认 <实例根>/adapters（自包含实例已 vendor），免传引擎路径。
```

## 怎么接进 runtime（事件驱动，无定时器、无自动 hook）

**runtime 中立**：开/关、落地路径、注入点全从 `adapters/<runtime>/adapter.yaml` 的 `runtime_context` 块读，
`wire-context.py` 通用照办。给新 agent（openclaw…）上这套 = 写个 adapter 块，核心零改动。

接入只两件事，且**触发都是真实事件、不是时钟**：

1. **bootstrap 时写一次小抄**：新 agent 上手（`substrate-bootstrap`）末尾跑一次 `wire-context.py --apply`，把 `.hermes.md`（或该 runtime 的 `digest_file`）落地。其中**路由表 + 房规 + 各区地图**是稳定的——写一次就长期管用（runtime 每条消息原生加载它）。
2. **写库后刷新**：之后**不需要定时器**——`house-rules.md` 里有一条常驻规则，要求 agent **每次写完库就再跑一次 `wire-context.py --apply`**，让新记忆/待办立刻进下一条消息。远程别人改的库，靠开工自检里的 `git pull`（见 `governance/bootstrap.md`）在你下次用库时带进来。

> 为什么不用「每会话自动跑的 shell hook」：那种 hook 的首次授权是 **TTY-only**，纯聊天网关答不了，要靠 `hooks_auto_accept: true` 放宽安全——得不偿失。改用「写库即刷 + 用库前 pull」的事件驱动，纯走 agent 平时的动作，不碰那道安全门。
>
> 没有专属 adapter 的 agent → 走 `generic-filesystem` 的 `runtime_context` 兜底（显式开启）。

接好后**日常零操作**：定时刷新 + 开工注入，新记忆/新待办/新 skill 自动流入。

## 只灌一部分（给 cc/codex 选择性开）

不想要整张小抄、只要路由表时，可在注入前裁掉「关于主人」段（避免把个人记忆塞进写代码会话）。具体裁法在 adapter 文档里。

## 红线

- 引擎只含**生成器 + 房规模板 + 占位**；真实小抄内容只在主人私有实例里**现拼**，绝不入引擎仓库。
- 小抄含 `memory/about-owner/`（`privacy: sensitive`）——只注入进**主人自己机器上**的 runtime，不外发。
