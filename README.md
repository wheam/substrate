# Substrate

> **个人 AI agent 舰队的「共享状态层」引擎**——一个 git 原生、可被 agent 操作、可审计、可自描述、可安全升级的模板与机制。
> 状态：**积极开发中**（P0 契约与模板已落地，见底部）。这是从设计（`docs/BUILD-PLAN.md`）抽象出的**开源引擎**，本身**不含任何个人内容**——引擎对所有用户中立。

---

## 这是什么 / 不是什么

**是**：让任何人都能搭起自己那套「多 agent 共维的个人状态仓库」的**引擎 + 模板 + 参考 skill + adapter + 迁移**。
它把"怎么维护一个被多个 agent / 多台机器长期共写的仓库"沉淀成可复用机制：治理层、分区注册、准入审查、skill 分发、记忆共享、防退化体检、安全升级。

**不是**：又一个 Obsidian、又一个 RAG。它卖的是 **shared state layer**——知识、记忆、技能、清单、规则、审计，都在一个**可版本化、可迁移、可被 agent 操作**的系统里，不被锁进任何平台。

> 目标用户：有多个 agent/runtime、频繁让 agent 代办、要跨设备一致状态、关心数据可迁移的人。

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
- [ ] 公开前 gate：LICENSE 定稿

> 开发依据见 `docs/BUILD-PLAN.md`（P0–P5 完整路线）。
