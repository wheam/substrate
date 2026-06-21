# Substrate

> **个人 AI agent 舰队的「共享状态层」引擎**——一个 git 原生、可被 agent 操作、可审计、可自描述、可安全升级的模板与机制。
> 状态：**P0–P5 全部落地**，`sh tests/run-tests.sh` 70 个零依赖回归测试全绿；积极维护中。这是从设计（`docs/BUILD-PLAN.md`）抽象出的**开源引擎**，本身**不含任何个人内容**——引擎对所有用户中立。

---

## 这是什么 / 不是什么

**是**：让任何人都能搭起自己那套「多 agent 共维的个人状态仓库」的**引擎 + 模板 + 参考 skill + adapter + 迁移**。
它把"怎么维护一个被多个 agent / 多台机器长期共写的仓库"沉淀成可复用机制：治理层、分区注册、准入审查、skill 分发、记忆共享、防退化体检、安全升级。

**不是**：又一个 Obsidian、又一个 RAG。它卖的是 **shared state layer**——知识、记忆、技能、清单、规则、审计，都在一个**可版本化、可迁移、可被 agent 操作**的系统里，不被锁进任何平台。

> 目标用户：有多个 agent/runtime、频繁让 agent 代办、要跨设备一致状态、关心数据可迁移的人。

---

## 快速上手（起手 4 步）

你需要两个 git 仓库：**引擎**（这个仓库，公开，只含机制）+ **你的实例**（私有，放你的知识/记忆/技能/清单）。下面 4 步从零搭起你自己的个人知识库。

**前置**：`git`、`python3`（**标准库即可，无需 pip 装任何包**）、一个能读 skill 的 agent runtime（Claude Code、Codex、Hermes…）。

```sh
# 1) 拿引擎（或在 GitHub 上 Fork 到你账号）
git clone https://github.com/<you>/substrate.git && cd substrate

# 2) 脚手架你自己的私有实例（自包含：自带 template 骨架 + vendored 维护 skill + adapters）
./init-instance.sh ~/my-cortex my-instance
cd ~/my-cortex && git init && git add -A && git commit -m "init my substrate instance"
#   然后在 GitHub 建一个【私有】仓库，把它 push 上去（你的个人内容不应公开）

# 3) 把维护 skill 装进你的 agent runtime（按 runtime 选择性安装）
python3 ~/my-cortex/skills/substrate-sync/sync.py \
        --src ~/my-cortex/skills --runtime claude-code --apply
#   换 runtime 就改 --runtime codex / hermes …（支持的见 adapters/）

# 4) 让 agent 上手：对它说「帮我接入这个个人仓库 / 这个库是什么」
#    → 触发 substrate-bootstrap：读宪法+分区、配本地身份、自检对齐，然后就能替你维护了
```

做完这 4 步，你就有了一个**多 agent 共维、git 原生、可迁移**的个人状态层。换机器/换 agent，只要 `git clone 你的实例` + 重跑第 3 步装 skill，即同一套能力。

## 日常怎么用（和 agent 对话）

装好后用自然语言让 agent 代你维护——它会触发对应 skill：

| 你说 | 触发的 skill |
|---|---|
| 「记一下 X / 存进知识库 / 这个值得记录」 | `substrate-curator`（增删改知识页 + 自动互链 + 同步目录索引） |
| 「收藏这家餐厅 / 加到书单」 | `substrate-collections`（结构化收藏：CSV 为源 + 人读分片） |
| 「记住我…/ 我的偏好是…」 | `substrate-memory`（跨 agent 共享的「关于主人」记忆） |
| 「加个待办 / 我的 todo」 | `substrate-todo` |
| 「这个要不要存 / 存哪 / 算知识还是 skill」 | `substrate-intake`（准入分类） |
| 「把这些笔记导进库」 | `substrate-import`（批量导入 markdown/vault） |
| 「体检一下库 / 库有没有问题」 | `substrate-doctor`（断链/孤儿/索引漂移/计数，只读） |
| 「装/更新 skill / pull 后对齐」 | `substrate-sync` |

> **多机/多 agent 保持一致**：每次开工让 agent 跑「自检例程」（`git pull` → `sync --check` → 落后则 `--apply` → `doctor`）。`sync --check` 会顺带 `git fetch` 比对远程，**本地落后也能发现**，不会误判已最新。想全自动，就给你的 runtime 接一个**会话启动钩子**跑这套（见 `template/governance/bootstrap.md`）。

## 怎么升级（引擎出新版，不丢数据）

引擎发新版后，在**你的实例**里：

```sh
# 1) 刷新实例里 vendored 的维护 skill 到新引擎
/path/to/substrate/init-instance.sh --refresh ~/my-cortex
# 2) 让 agent 跑迁移：对它说「升级库 / 迁移到新版本」→ 触发 substrate-migrate
#    （有序/幂等/可验证/可回滚；先打 git tag 快照、doctor 前后校验；多机只在 migration_leader 上跑）
```

迁移当**数据库迁移**做，任何一步都不丢数据（详见 `docs/BUILD-PLAN.md` §9）。

---

## 核心抽象：Engine / Instance 分离

这是本项目的灵魂，也是它能开源的前提：

| | Engine（本仓库，可复用、可开源） | Instance（用户私有的个人状态仓库） |
|---|---|---|
| 内容 | 机制、模板、schema、参考 skill、adapter、**迁移** | 知识页、收藏、记忆、TODO、projects、fleet、私有 skill |
| 可见性 | 公开 | 私有（你自己的仓库） |
| 约束 | **不得依赖任何用户的偶然事实**（目录命名以外） | 在 engine 之上叠自己的内容 |

引擎决定"怎么维护"，instance 决定"维护什么"。引擎与实例是**两个独立的 git 仓库**。

---

## 三层模型（control / data / execution plane）

- **Control plane** — `template/governance/`：宪法、分区注册、准入、上手协议、版本。
- **Data plane** — `template/{knowledge,collections,memory,projects,...}`：用户长期个人 context。
- **Execution plane** — `template/skills/` + 本地清单：能做事的东西 + 本地状态（不入库）。

> 概念分层，instance 落地时不必照搬目录名。术语见 `docs/concepts.md`。

---

## 目录结构

```
substrate/
├── README.md  LICENSE  CONTRIBUTING.md
├── ENGINE_VERSION       # 引擎版本（迁移区间计算的源头；实例侧记 governance/SUBSTRATE_VERSION）
│
├── docs/                # 引擎文档（给人读）
│   ├── BUILD-PLAN.md    #   完整设计 + 开发路线 P0–P5（开发依据）
│   ├── architecture.md  #   设计原理：三层模型 + 防退化 + 准入 + 规模化
│   └── concepts.md      #   术语单一源：zone / governance / admission / Agent Packet / migration …
│
├── template/            # ★ init 时脚手架进用户仓库的「instance 骨架」
│   ├── README.md            # instance 入口：顶部「agent 必读」横幅 + zone 级索引
│   ├── .gitignore           # 默认忽略：本地清单/缓存/generated/嵌套外部 repo
│   ├── governance/          # control plane
│   │   ├── CONSTITUTION.md   #   少而硬的全局不变量 + 「新增类型」procedure
│   │   ├── zones.md         #   分区注册表（顶部可解析 YAML 块 + 人话）
│   │   ├── admission.md     #   入库四问 / 四去向 / skill 风险分级
│   │   ├── bootstrap.md     #   新 agent 上手协议
│   │   ├── architecture.md  #   本实例的设计逻辑（用户填）
│   │   └── SUBSTRATE_VERSION #  本实例基于的引擎版本（迁移用）
│   ├── fleet/README.md      # 设备清单 + 角色（实例数据）
│   ├── skills/              # execution plane：README + _registry + _incoming/
│   ├── memory/about-owner/  # 跨 agent 共享的「关于主人」记忆（通用槽位）
│   ├── collections/         # 通用收藏（行式 canonical + 索引）
│   ├── projects/            # 个人非代码项目
│   ├── knowledge/           # 知识页（分类用户自定）
│   └── raw/                 # 原始素材（只读）
│
├── schemas/             # ★ 机器可解析「契约」（doctor / sync / migrate 解析它们，不猜 markdown）
│   ├── zone.schema.yaml          # zone 注册项字段（含 graduation）
│   ├── skill-manifest.schema.yaml#  skill 元信息（risk_level / capabilities / target_runtimes）
│   ├── registry.schema.yaml      # 第三方 skill registry 条目
│   └── migration.schema.yaml     # 版本迁移：有序/幂等/可验证/可回滚
│
├── skills/              # ★ 引擎参考 skill 套件（substrate-*，见 skills/README.md；P1+ 逐个实现）
├── adapters/            # ★ 可插拔 runtime 适配器（声明式：装哪/怎么探测/清单存哪）
├── migrations/          # ★ 版本迁移（P3）
└── examples/minimal/    # 最小可跑示例 instance（中立假数据）
```

---

## 操作 = skill（skills-first）

**Substrate 是 agent-native 的**：所有操作的第一公民是参考 skill（agent 读 skill 即执行），**不依赖编译型 CLI / Node / Python 运行时**。

| 操作 | 负责的 skill |
|---|---|
| 脚手架新实例 | `substrate-bootstrap`（+ `template/` 拷贝） |
| 防退化体检（断链/孤儿/索引漂移/registry/毕业阈值） | `substrate-doctor` |
| 按角色选择性装 skill | `substrate-sync` |
| 内容分类 + 审查 `_incoming/` 回流件 | `substrate-intake` |
| 批量导入已有内容 | `substrate-import` |
| 跨引擎版本安全迁移 | `substrate-migrate` |

> doctor / migrate 的**确定性**靠 skill **内嵌零安装 shell**（grep/sort/comm + python3 标准库），不靠二进制。CI / 无 agent 场景**直接跑脚本**（`doctor.py` / `sync.py`）即可——**没有** `substrate` CLI 这层壳。

---

## 升级不丢数据（迁移是一等公民）

引擎会演进（治理约定、schema、zone 布局变化）。一个基于引擎 vX 的实例升到 vY，**当数据库迁移做**：有序、命名、幂等、可验证、可回滚（契约见 `schemas/migration.schema.yaml`）。任何迁移不丢数据——git tag 快照 + doctor 前后校验不变量 + 模糊内容进隔离区。详见 `docs/BUILD-PLAN.md` §9。

---

## 起源

本引擎按 `docs/BUILD-PLAN.md` 的设计落地。设计者自己有一个朴素的私有知识库作为需求来源与**测试素材**（不随本仓库公开，也不被引擎依赖）。**抽象顺序**：先把 engine / instance / local / generated / forbidden 边界划干净，再做 template + 参考 skill + adapter + 迁移；skill 市场 / 托管同步 / Web UI 等**现在不做**。

---

## 状态

- [x] 目录骨架 + 结构设计
- [x] **P0**：4 个 schema 定稿（+ `zone.schema` graduation）；`docs/concepts.md` 术语表；`template/` 填实（governance 五件套 + 各 zone README 含 Agent Packet + skills README/_registry + fleet）；`examples/minimal` 立起；`ENGINE_VERSION`
- [x] **P1**：核心闭环 `substrate-curator/sync/doctor/bootstrap`，跑通 clone→bootstrap→装 skill→读写→doctor 通过
- [x] **P2**：准入与导入（`substrate-intake` / `substrate-import` + generic-md/obsidian 来源适配器）
- [x] **P3**：迁移机制（`migrations/` + `substrate-migrate`，含回滚 + 多机幂等 + 引擎自我保护）
- [x] **P4**：适配器（generic-filesystem + claude-code 做实，codex/hermes/obsidian 声明）
- [x] **P5**：收尾 skill（collections / memory / todo）
- [x] LICENSE（MIT）+ 公开 README（快速上手 / 日常用 / 升级）

> 开发依据见 `docs/BUILD-PLAN.md`（P0–P5 完整路线）。
