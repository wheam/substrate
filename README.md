# substrate（工作名）

> **个人 AI agent 舰队的「共享状态层」引擎**——一个 git 原生、可被 agent 操作、可审计、可自描述的模板与机制。
> 状态：**设计/脚手架阶段**。这是一个从真实私有 instance 抽象出来的**开源引擎**，本身**不含任何个人内容**。

---

## 这是什么 / 不是什么

**是**：让任何人都能搭起自己那套「多 agent 共维的个人状态仓库」的**引擎 + 模板 + 参考 skill**。
它把"怎么维护一个被多个 agent / 多台机器长期共写的仓库"沉淀成可复用机制：治理层、分区注册、准入审查、skill 分发、记忆共享、防退化体检。

**不是**：又一个 Obsidian、又一个 RAG。它卖的是 **shared state layer**——知识、记忆、技能、清单、规则、审计，都在一个**可版本化、可迁移、可被 agent 操作**的系统里，不被锁进任何平台。

> 目标用户：有多个 agent/runtime、频繁让 agent 代办、要跨设备一致状态、关心数据可迁移的人。

---

## 核心抽象：Engine / Instance 分离

这是本项目的灵魂，也是它能开源的前提：

| | Engine（本仓库，可复用、可开源） | Instance（用户私有的个人状态仓库） |
|---|---|---|
| 内容 | 机制、模板、schema、参考 skill、adapter | 知识页、收藏、记忆、TODO、projects、fleet、私有 skill |
| 可见性 | 公开 | 私有（你自己的仓库） |
| 约束 | **不得依赖任何用户的偶然事实**（目录命名以外） | 在 engine 之上叠自己的内容 |

引擎决定"怎么维护"，instance 决定"维护什么"。

---

## 三层模型（control / data / execution plane）

引擎按三层组织职责（概念分层，instance 落地时不必照搬目录名）：

- **Control plane** — `template/governance/`：宪法、分区注册、准入、上手协议。
- **Data plane** — `template/{knowledge,collections,memory,projects,...}`：用户长期个人 context。
- **Execution plane** — `template/skills/` + 本地清单：能做事的东西 + 本地状态。

---

## 目录结构

```
substrate/
├── README.md            # 本文件
├── LICENSE              # 开源许可（占位 MIT，待定）
├── CONTRIBUTING.md      # 贡献指南（占位）
│
├── docs/                # 引擎文档（给人读）
│   ├── architecture.md  #   设计原理：三层模型 + 防退化 + 准入 + 规模化毕业路径
│   ├── concepts.md      #   术语：zone / governance / admission / skill registry / Agent Packet
│   └── faq.md           #   常见问题
│
├── template/            # ★ 脚手架进用户仓库的「instance 骨架」（init 时拷贝）
│   ├── README.md        #   instance 入口：顶部带「agent 必读」横幅，指向 governance/
│   ├── .gitignore       #   默认忽略：本地清单/缓存/generated/嵌套外部 repo
│   ├── governance/      #   control plane 模板
│   │   ├── CONSTITUTION.md   # 少而硬的全局不变量 + 「新增类型」procedure
│   │   ├── zones.md         # 分区注册表（顶部可解析 YAML 块 + 人话）
│   │   ├── admission.md     # 入库四问 / 四去向 / skill 风险分级
│   │   ├── bootstrap.md     # 新 agent 上手协议
│   │   └── architecture.md  # 本 instance 的设计逻辑（用户填）
│   ├── fleet/README.md      # 设备清单 + 角色（main-dev/headless-dev/...）
│   ├── skills/
│   │   ├── README.md        # 本区规则
│   │   ├── _registry.md     # 第三方 skill 清单（URL + pin + 目标 runtime）
│   │   └── _incoming/       # 自动回流隔离区，过 admission 才晋升
│   ├── memory/about-me/     # 跨 agent 共享的「关于主人」记忆（默认仅特定 runtime）
│   ├── collections/         # 通用收藏（行式 canonical + 索引）
│   ├── projects/            # 个人非代码项目
│   ├── knowledge/           # 知识页（concept/entity/comparison/insight 由用户自定）
│   └── raw/                 # 原始素材（只读）
│
├── schemas/             # ★ 机器可解析的「契约」（doctor / sync 依赖它们，不靠猜 markdown）
│   ├── zone.schema.yaml         # zone 注册项字段
│   ├── skill-manifest.schema.yaml  # skill 元信息（含 risk_level / target_runtimes）
│   └── registry.schema.yaml     # 第三方 skill registry 条目
│
├── skills/              # ★ 引擎自带的参考 skill 套件（instance 可直接装）
│   ├── bootstrap/       #   新 agent 自举
│   ├── skill-sync/      #   按角色选择性安装 + 维护本地清单 + 回流到 _incoming
│   ├── admission/       #   守门：入库四问 + skill 风险分级 + 晋升/转 audit
│   ├── wiki-doctor/     #   增量体检：断链/孤儿/索引漂移/registry 风险
│   └── collections/     #   收藏维护（行式数据 + 索引同步）
│
├── adapters/            # ★ 可插拔 runtime 适配器（把抽象的「装 skill / 读规则」落到具体 runtime）
│   ├── claude-code/     #   ~/.claude/skills 等
│   ├── codex/           #   AGENTS.md / Codex skill 路径
│   ├── hermes/          #   ~/.hermes/skills 等
│   └── generic-filesystem/  # 兜底：纯文件系统
│
├── cli/                 # substrate CLI（init / doctor / sync-skills / admit / new-zone）
│   └── README.md
│
└── examples/
    └── minimal/         # 最小可跑示例 instance
```

---

## CLI 设想（待实现）

```
substrate init         # 把 template/ 脚手架成一个新 instance 仓库
substrate doctor       # 跑 wiki-doctor 体检
substrate sync-skills  # 按本机角色选择性安装/更新 skill
substrate admit        # 审查 _incoming/ 里的回流 skill，晋升或转人工
substrate new-zone     # 按 procedure 新增一个内容类型
```

---

## 起源与抽象顺序

本引擎从一个真实运行的私有 instance 中提炼而来——那个私有仓库既是需求来源，也是试验田。
（其设计文档保存在引擎仓库之外的私有工作环境中，**刻意不随本仓库公开**。）

**抽象顺序**（不急着做平台）：
1. 先在私有 instance 里把 engine / instance / local / generated / forbidden 边界划干净（这一步本身就澄清设计）。
2. 之后：把可复用部分提到本仓库，做 template + CLI + adapter。
3. 更远：才谈 skill 市场 / 托管同步 / Web UI——现在**不做**。

---

## 状态

- [x] 目录骨架 + 结构设计（本 README）
- [ ] schemas/ 契约定稿
- [ ] template/ 各文件填实
- [ ] 参考 skill 套件实现
- [ ] adapter 接口定义
- [ ] CLI 实现

> 这是设计脚手架，**尚未实现**。任何落地等私有 instance 跑顺、边界验证后再提取。
