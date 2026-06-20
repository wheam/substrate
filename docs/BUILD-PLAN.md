# Substrate — 完整设计与开发方案（build spec）

> **给开发 session 的说明**：这是 **Substrate** 开源引擎的完整设计 + 开发方案。读完即可着手开发。
> 脚手架就在本仓库（Substrate 引擎）。设计原理见 `./architecture.md`、`./concepts.md`。
> 命名：引擎 = **Substrate**；用户自己的实例 = `<your-instance>`（用户自取，私有）；skill 套件命名为 `substrate-*`。
> 状态：设计完成、待开发。本文件是开发依据。

---

## 0. 一句话

**Substrate = 个人 AI agent 舰队的「共享状态层」引擎**：一个 git 原生、可被 agent 操作、可审计、自描述、可安全升级的模板与机制。
知识 / 记忆 / 技能 / 清单 / 规则 / 审计都在一个**可版本化、可迁移、不锁平台**的系统里。它随仓库自带「怎么维护自己」的规则与工具，让任何新 agent clone + 读 README 就能上手。

---

## 1. 核心命题 + Engine / Instance 分离

个人 agent 舰队（多机器 × 多 runtime × 多 agent）缺一层共享状态层。Substrate 提供它。

**最高层抽象（地基）：Engine / Instance 分离**

| | Engine（本项目，开源） | Instance（用户私有，如 <your-instance>） |
|---|---|---|
| 内容 | 机制、模板、schema、参考 skill、adapter、迁移 | 知识、收藏、记忆、清单、项目、fleet、私有 skill |
| 可见性 | 公开 | 私有 |
| 约束 | **不依赖任何用户的偶然事实** | 叠在引擎之上 |

引擎决定「怎么维护」，实例决定「维护什么」。划清这条边界是所有其它设计的前提。

---

## 2. 三层模型（control / data / execution plane）

| 层 | 回答 | 装什么 |
|---|---|---|
| **Control plane** | 什么能被写/写到哪/谁写/怎么验证 | `governance/`：宪法、zones、admission、bootstrap、architecture、版本 |
| **Data plane** | 用户长期个人 context 是什么 | 知识、collections、memory、projects、fleet |
| **Execution plane** | 能做事的 + 本地状态 | `skills/`（可版本化）+ 本地清单/缓存/身份（不入库） |

> 概念分层，不强制成目录名。

---

## 3. 仓库骨架

### 3.1 Engine 仓库（Substrate 本体，开源）
```
substrate/
├── README.md  LICENSE  CONTRIBUTING.md
├── docs/                 # architecture / concepts
├── template/             # init 时脚手架成用户 instance 的骨架（见 3.2）
├── schemas/              # 契约：zone / skill-manifest / registry / migration
├── skills/               # 参考 skill 套件（substrate-*，见 §8）
├── adapters/             # 可插拔：claude-code / codex / hermes / obsidian / generic-filesystem
├── migrations/           # 版本迁移（见 §9）
└── examples/minimal/     # 一个跑通的最小 instance
```

### 3.2 Instance 骨架（由 `template/` 脚手架）
```
<instance>/                # 如 <your-instance>
├── README.md             # 入口：顶部「AGENT 必读」横幅 + zone 级索引
├── .gitignore            # 本地清单/generated/嵌套外部 repo
├── governance/           # ── control plane ──
│   ├── CONSTITUTION.md    #   少而硬的全局不变量 + 「新增类型」procedure
│   ├── zones.md          #   分区注册表（顶部可解析 YAML 块 + 人话）
│   ├── admission.md      #   入库四问 / 四去向 / skill 风险分级
│   ├── bootstrap.md      #   新 agent 上手协议
│   ├── architecture.md   #   本 instance 的设计逻辑
│   └── SUBSTRATE_VERSION #   本实例基于的引擎版本（迁移用）
├── fleet/                # 设备清单 + 每台机角色
├── <knowledge zones>/    # ── data plane ── 知识页（用户自定分类）
├── collections/          #   通用收藏（行式 canonical + 索引）
├── memory/about-owner/   #   跨 agent 共享记忆（about-owner = 通用槽位；主人名写在内容里，不入 folder 名）
├── projects/             #   个人非代码项目
├── skills/               # ── execution plane ──
│   ├── _registry.md      #   第三方 skill 清单（URL+pin，代码不入库）
│   ├── _incoming/        #   自动回流隔离区，过 admission 才晋升
│   └── <skill>/          #   自己写的/已晋升的
└── raw/                  # 原始素材（只读）
```

> **通用命名（不绑定具体用户）**：共享记忆槽位叫 **`memory/about-owner/`**——是个**稳定的通用槽位**，「主人是谁」（名字/偏好）写在**内容**里，不进 folder 名。这样 skill 不硬编码任何人名，引擎与所有实例一致。（实例里它也叫 `about-owner`，内容写 `owner: <你的名字>`。）
>
> **引擎 vs 实例的边界（机器/fleet）**：引擎只提供**通用的 `fleet/` 槽位 + 一套"每台机一次性接入"的通用机制**（clone→种子→sync→bootstrap，见 §10）。**具体有哪几台机器、各自角色，是实例数据**，写在用户自己实例的 `fleet/` 里，**不进引擎**。

- **`CONSTITUTION.md`**：所有维护 skill 引用的唯一权威——pull/commit/汇报、写前勘察绝不重复建页、命名与 frontmatter、≥2 wikilink、目录表同步、矛盾 `contested` 双留、**新增类型 5 步 procedure**。改规则只改这一处。
- **`zones.md`**：分区注册表，**顶部放可解析 YAML 块**（字段最小集：`id/path/schema/maintainer_skill/readers/writers`，可加 `disposition/privacy/graduation`），后面写人话。doctor/sync 解析它，不猜 markdown。
- **`admission.md`**：准入规则（见 §7）。
- **`bootstrap.md`**：新 agent 上手协议（见 §10）。
- **`architecture.md`**：设计逻辑。
- 规则**烘焙进 skill**——skill 即「可执行的宪法」，agent 照 skill 做即守规矩，不必每次重读宪法。

---

## 5. 索引模型（两级 + Agent Packet）

- **根 README** 只做 **zone 级**路由；每个 zone 的 README 管**本区文件级**索引。单点巨表不再是退化源。
- 每个 zone README 顶部一个极短 **Agent Packet**（固定字段：zone / 维护 skill / canonical 在哪 / 写前查什么 / 写后更新什么 / doctor 检查项）。**稳态读取 = O(相关 zone)，永不 O(全库)**——这是 context 经济的关键。

---

## 6. Skills 分发系统

- **三类**：自己写的（纯文件，跟仓库走）｜第三方（`_registry.md` 只存 URL+pin，代码不入库，安装时 clone）｜agent 自总结的（先自动回流到 `_incoming/`，过 admission 才晋升）。
- **安装（管家模式）**：一台机器当管家，按 **fleet 角色 + skill 声明的目标 runtime** **选择性安装**（不 install-all）到各 runtime；本地维护「装了啥+版本」清单（**不入库**）。
- **多 runtime 变体**：一个 skill 文件夹内同放各 runtime 版本，靠约定区分；skill 带 manifest 声明目标 runtime。

### 6.1 第三方 skill 引用以什么形式存在
就是一个**清单文件 `skills/_registry.md`**——每个第三方 skill 一条记录（顶部一个可解析 YAML 块，后面人话），字段见 `schemas/registry.schema.yaml`：`name / upstream_git_url / pin(tag/commit) / target_runtimes / install_paths / notes`。**代码不进库，库里只有指针**（URL + 钉的版本）。自己写的 skill 则是 `skills/<name>/` 里的真文件。

### 6.2 一台新机器装了 Claude Code，怎么把所有 skill 用上
Claude Code「用」一个 skill = 该 skill 在它的 skill 目录（`~/.claude/skills/`）里，它就能自动发现并调用。所以问题只是**怎么把 skill 装进那个目录**——这就是 `substrate-sync` 干的事：

1. **clone 实例仓库**到本机（先配好 SSH-over-443）。
2. **种子一次**：把 `substrate-bootstrap` + `substrate-sync` 放进 CC 的 skill 目录（一行种子安装脚本 cp/curl 做这步；解决"要 sync 先得有 sync"的鸡生蛋）。
3. **跑 sync**：读 `skills/`（自己的 → 直接拷进 `~/.claude/skills/`）+ `_registry.md`（第三方 → 按 pin 从上游 clone → 拷进去），**只装 `target_runtimes` 含 `claude-code` 且符合本机角色的**；多 runtime skill 取 CC 变体。
4. 之后 CC 即可在 skill 目录里发现并调用全部适用 skill；本地写一份「装了啥+版本」清单，下次增量更新。

> 谁来跑 sync：在有管家的机器上由管家统一装到各 runtime，CC 不用自己动；**纯 CC 机器**则直接跑 `substrate-sync` 的 `sync.py` 自助。

---

## 7. 内容准入 + intake 分类器（灵魂）

**章程**：服务「持久的、可文件化的、跨 agent 有共享价值的个人 context，以及维护它的规则与工具」。

- **入库四问**：持久？属于个人 context？可文件化且适合 git？跨 agent 有共享价值？
- **四种去向**：**Canonical**（进库成事实源）｜**Reference**（只存引用+摘要）｜**Local-only**（只留本机）｜**Forbidden**（密钥/凭据/敏感原文/大二进制，永不进库）。
- **zone vs page**：仅当有独立 schema+维护行为+访问模式才开新顶层 zone，否则是已有 zone 的一页/一行。
- **去重**：精确键 / 语义 / 结构三层；相似就合并不新建。
- **多媒体 = Reference，不当云盘**（给 agent 用的，不是网盘）：二进制本体不进库，只放引用+元数据+**文字代理**（转写/OCR/描述/标签）；小图可 git-lfs；agent 操作文字代理不碰字节。
- **`substrate-intake`（分类器/守门，两张脸）**：① 给人丢进来的新内容出安置建议（四去向/落哪 zone/该否拆 skill/剔敏感位）；② 守门自动回流的 skill（风险分级：只读写 markdown 可自动晋升；跑 shell/改系统/联网/装依赖/碰 secrets/改其它 skill 或 governance 的一律人工 audit）。判 skill 还是知识的尺：想**读**它=知识，想让 agent **反复做**它=skill。

---

## 8. 规模化 + 毕业机制

**为毕业而设计，不为固定规模**。三件分开：
1. **路径先声明**：zones.md 里写 `graduation:` 触发条件（如 `collections: rows>2000 → 分片 JSONL；需 join → SQLite cache`）。
2. **doctor 监测阈值**：越线发 finding（"已 2300 行，建议毕业"）。
3. **执行 deliberate**：doctor 只提议不自动迁；由迁移 skill / 人确认后做。

各 zone 毕业路径：结构化数据 行式 canonical（CSV→JSONL）→ 本地 SQLite **缓存** →（极端）canonical-DB；知识 目录表→wikilink 图+tags+embedding；skill 选择性安装+pin。**SQLite 永远先做缓存，不当 canonical。**

---

## 9. ★长期升级 / 版本迁移机制（最重要）

**问题**：引擎会演进（治理约定、schema、zone 布局、skill API 变化）。一个基于引擎 vX 的实例要升到 vY，**不能丢数据、不能破坏**，且要在**多机器**上各自安全执行。怎么让 agent 在升级被触发时知道**该做什么、怎么迁、不丢东西**？

**把它当数据库/框架迁移做：**

1. **版本化**：引擎有 `ENGINE_VERSION`；实例在 `governance/SUBSTRATE_VERSION` 记录自己基于的版本（committed）。
2. **迁移即一等公民**：引擎 `migrations/` 目录，每个迁移是有序、命名、**幂等**、可验证、可回滚的 vN→vN+1 变换（契约见 `schemas/migration.schema.yaml`：id / from / to / steps[{action,verify}] / idempotent / preserves / rollback / risk_level）。
3. **升级流程（`substrate-migrate` skill 执行）**：
   - a. **检测** `instance.version < engine.version` → 有 pending 迁移。
   - b. **不静默执行**：读出区间内所有迁移，生成**迁移计划**呈现给人。
   - c. **备份**：打 git tag `pre-migrate-<from>`（git 天然快照 = 零成本回滚点）。
   - d. **按序应用**，每个迁移幂等，每步跑自带 verify。
   - e. **整体验证**：跑 `substrate-doctor` 校不变量（内容计数、zone 注册、链接完整、frontmatter 合规）对比迁移前后。
   - f. **成功** → commit + bump `SUBSTRATE_VERSION` + push；**失败** → `git reset` 回 `pre-migrate-<from>` tag，报告，转人工。
   - g. 任何无法自动判定的内容 → 进隔离区/audit，**不静默删**。
4. **不丢信息的多重保证**：git 全历史 + pre-migrate tag 永远可回滚；迁移以变换/追加为主，destructive 必须先备份且 high-risk→人工；doctor 前后对比不变量，对不上就拒绝回滚；模糊内容隔离待审。
5. **多机器协调**（呼应 §12 / 设备）：迁移幂等 + 版本闸门——管家机器迁移并 bump version+push 后，其它机器 pull 看到版本已最新即**跳过**，不重复迁；并发想迁则 git push 冲突，后者 pull 后发现已迁即跳过。建议在 `fleet/` 标一台 `migration_leader` 专责执行。
6. **doctor 双重角色**：既是日常防退化体检，也是**迁移的测试套件**。
7. 每个引擎版本带 CHANGELOG + 机器可读迁移清单，agent 读它生成计划。

---

## 10. ★新用户上手 + 导入助手（你新提的点 1）

要分清**两种迁移**：①「跨引擎版本」升级（§9）；②「把已有的旧东西搬进一个全新 Substrate 实例」（本节）。后者若手动做很痛，所以要有**导入助手**。

**`substrate-import`（批量上手迁移器）**：
- **职责**：把用户现有的一堆东西（散落 markdown、文件夹、Obsidian vault、Notion/Apple Notes 导出、纯文本）批量搬进一个新实例，免手动苦力。
- **流程**：扫描来源 → 对每条用 `substrate-intake` **批量分类**（四去向/落哪 zone/该否拆 skill/剔敏感位）→ 生成**映射计划**（dry-run）→ 人审批 → 执行（放文件、补缺失 frontmatter、建初始索引 + Agent Packet、注册 zone、跑 doctor）→ commit。
- **关键**：复用 `intake`（单条分类器的批量版）+ **来源适配器**（Obsidian vault / Notion 导出 / 纯 md 文件夹 / Apple Notes 导出…）；幂等 + dry-run + 审批闸门；模糊的进隔离区，**不批量塞垃圾**。

**完整 init 流程（别人 clone 引擎后）**：
1. 拿引擎：`git clone`（agent-native 主路径）。
2. **`substrate-bootstrap` skill 脚手架**：把 `template/` 拷成新实例仓库（治理模板、空 zone、skills 结构、.gitignore、SUBSTRATE_VERSION）；交互填占位（实例名、用哪些 runtime、先开哪些 zone）。
3. 用户 `git init` 自己的实例 + 推到**自己的**私有远程（engine 与 instance 是两个仓库）。
4. **可选：`substrate import <source>`** 把已有内容搬进来（本节）。
5. agent 跑 `substrate-bootstrap`：读宪法/zones → 配本地身份 → `substrate-sync` 装参考 skill 到 runtime。
6. 个性化：改 CONSTITUTION/zones，开始用。

---

## 11. ★工具兼容 / Obsidian 等（你新提的点 2）

**核心策略：兼容靠「开放格式」，不靠「专属集成」。** Substrate 的 data plane 就是**纯 markdown + YAML frontmatter + `[[wikilinks]]` + CSV/JSONL**——这是所有 PKM 工具的最小公约数。

- **Obsidian 即插即用**：它本就读「一堆带 `[[wikilink]]` 的 md 文件夹」，所以任意 Substrate 实例**今天就能直接用 Obsidian 打开读写**，零迁移。
- **约定即接口**：链接用 `[[name]]`（Obsidian 原生）、frontmatter 用 YAML、结构化用 CSV/JSONL。任何 markdown 工具（Logseq、纯编辑器、grep、RAG）都能消费，零迁移。
- **可选 `adapters/obsidian/`**：只放「锦上添花」的工具专属配置——推荐的 vault 设置、把 `governance/`、`skills/_incoming/` 等下划线目录加进 Obsidian「排除文件」以减噪、graph 视图配置。`.obsidian/workspace.json` 等每设备布局 gitignore（多设备会冲突）。
- **专属格式的工具（如 Notion）**：通过**导入/导出适配器**互通（`substrate-import` 的 Notion-export 适配器把它搬进来；反向导出可后置）。
- **设计立场**：**Substrate 不绑定任何编辑器**——它是「git 仓库 + 开放格式约定」。工具是即插即用的「视图层」，agent 是「维护层」，我们只承诺开放格式；工具专属功能作可选 adapter。

---

## 12. 防退化（doctor）

1. 宪法单源 + 写入走 skill → 规则不漂移。2. 两级索引。3. zones 注册 + 新增类型 procedure。4. `substrate-doctor` 增量体检（断链/孤儿/索引漂移/缺 frontmatter/registry 风险）。5. bootstrap 一致上手。
**核心原则：协议失效时，结果应是「可修复的漂移」，而非「污染正式状态」。** 防御纵深：预防（入口横幅+走 skill）→ 检测（doctor）→ 隔离（危险写入/回流进 audit 区）→ 纠正（低风险自动修，高风险转人）。无法 100% 强制模型守协议，所以架构必须容错。
> **doctor 形态（skills-first）**：doctor 是 skill，不是二进制。为可复现 + 便宜 + 可 CI，它**内嵌零安装的确定性 shell**（`grep` 抽 `[[wikilink]]`〔先剥 inline code/代码块〕集合差找断链/孤儿、`sort`/`comm` 找漂移、python3 标准库做受限子集 frontmatter 解析〔不假设 PyYAML〕）。skill 是唯一真相源；它同时是迁移的测试套件（迁移前后跑同一套不变量）。**实现约束见 §15 P1。**

---

## 13. Skill 套件（substrate-*，自托管在 `skills/`）

| skill | 作用 |
|---|---|
| `substrate-curator` | 读写/维护知识页 + 执行宪法（**取代旧的 `personal-wiki` skill**） |
| `substrate-sync` | 按角色/registry 选择性安装到各 runtime + 本地清单 + 回流到 `_incoming` |
| `substrate-intake` | 内容分类器 + 自动回流守门（admission，§7） |
| `substrate-bootstrap` | 新 agent 自举 |
| `substrate-doctor` | 防退化体检 + 毕业阈值监测 + 迁移测试套件 |
| `substrate-import` | 批量把已有内容搬进新实例（§10） |
| `substrate-migrate` | 跨引擎版本安全迁移（§9） |
| `substrate-collections` | 收藏维护 |
| `substrate-memory` | 共享记忆读写 + 共享/本地边界 |
| `substrate-todo` | 待办维护 |

> 自托管：clone 实例即同时拿到维护工具，bootstrap 一气呵成。

---

## 14. 契约 / Schema（`schemas/`）
`zone.schema` · `skill-manifest.schema` · `registry.schema` · `migration.schema`（已在引擎仓库脚手架）。原则：字段最小集起步，doctor/sync/migrate 解析它们而非猜 markdown。

---

## 15. 开发路线（建议给开发 session）

- **P0 契约与模板**：定稿 schema（4 个 + `zone.schema` 补 `graduation`）；写 `docs/concepts.md` 术语表；填实 `template/`（governance 五件套 + 各 zone README 含 **Agent Packet**（两级索引）+ `skills/README`+`_registry` + `fleet/` + 入口 README + .gitignore + SUBSTRATE_VERSION）；立起 `examples/minimal`（中立假数据）当 doctor 靶子。〔已完成〕
- **P1 核心闭环**：`substrate-curator` + `substrate-sync` + `substrate-doctor` 最小版 + `substrate-bootstrap`；跑通「clone→bootstrap→装 skill→读写一篇→doctor 通过」。〔已完成〕
  - **doctor 实现约束（自检 `examples/minimal` 时已踩中、验证过）**：① **不假设 PyYAML**——frontmatter 用 python3 标准库做受限子集解析，或声明 PyYAML 为可选依赖、缺失时降级；② 抽 `[[wikilink]]` 集合**前必须先剥离 inline code（反引号）与 fenced code block**，否则教学/示例页里举例的 `[[...]]` 会被误判断链；③ 孤儿 / frontmatter 合规检查**豁免** `governance/*` 与 README/索引/分片这类结构页。
- **P2 准入与导入**：`substrate-intake`（分类+守门）+ `substrate-import`（含 generic-md / obsidian 来源适配器）；`_incoming` 隔离/晋升跑通。〔已完成〕
- **P3 迁移机制**：`migrations/` + `substrate-migrate`；写第一个真实迁移并验证 + 回滚 + 多机器幂等。〔已完成：示例迁移 0001 + 引擎自我保护护栏〕
- **P4 适配器**：`adapters/*` 接口定义——**先做 `generic-filesystem` + `claude-code`**，等第二个 runtime 真正逼出抽象再扩（codex/obsidian 等）。**无 CLI**：operations 第一公民是 skill；确定性逻辑就是**可直接跑的脚本**（`doctor.py` / `sync.py`），CI / 无 agent 直接跑脚本即可，不需要 `substrate` 壳。`examples/minimal` 已在 P0 立起，这里补到能过 doctor。〔已完成：声明式 adapter 接口 + sync 省略 `--target` 时自动读 adapter 推断目标（view-layer 拒绝）〕
- **P5 收尾 skill**：`collections` / `memory` / `todo`。〔已完成〕

---

## 16. 成败标准
**不是「装了多少机制」，而是「一个新 agent 能否低成本上手、一个新用户能否把已有东西低痛搬进来、写错了能否被发现和修复、升级时不丢东西」。**
