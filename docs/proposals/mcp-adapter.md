# 提案：Substrate MCP 网关（adapter `kind: gateway`）

> **状态**：提案 / 待实现（基于引擎 `ENGINE_VERSION = 0.3.0`）。
> **定位**：本文件是设计 + 工程 + 运维方案，**不含实现代码**。落地路线见 §6，按里程碑分阶段实现。
> **关系**：扩展 `BUILD-PLAN.md` §15 P4（适配器）——MCP 是逼出「第二类消费者」的 runtime，借它把 adapter 接口从「装 skill」扩到「访问/网关层」。
> **命名**：引擎 = Substrate；用户私有实例 = `<instance>`；常驻主机 = `<mcp-host>`（占位，不绑定任何具体机器）。

---

## 0. 一句话

给 Substrate 加一个 **MCP 网关**：让任意能说 MCP 的 agent（手机端、笔记本、服务器）**远程连到同一份实例**读写共享状态，**无需各自 `git clone`、各自装 skill**；治理规则随 MCP 下发，连从没装过 skill 的 agent 也被约束。它是叠在 git 仓库前面的**访问层**，不替代 git 分发式模型。

---

## 1. 背景与动机

### 1.1 现状：git 分发式（去中心）

引擎当前的多机模型是：每台机器 `git clone` 实例 → `substrate-sync` 把维护 skill 装进该机 runtime → skill 操作**本地文件** → 机器间靠 `git pull/push` 同步。

- **优点**：离线可用、每台机自洽、无单点故障。
- **代价**：**每台机 / 每个 agent 都要装一遍**（clone + sync skill）。runtime 越多越烦；不会说"装 skill"的 agent（如某些手机端）根本接不进来。

### 1.2 目标：再提供一种集中式接入

一台 24h 常驻主机 `<mcp-host>` 持有**唯一一份实例工作副本** + 跑 MCP server；其它 agent 远程连同一端点，共享同一份记忆/知识。**两种模型不互斥**——见 §1.4 混合部署。

### 1.3 三条必须遵守的项目约束

1. **Engine / Instance 分离**：MCP server 是**引擎机制**，"操作某个实例"，但**不依赖任何用户偶然事实**——实例路径、鉴权、fleet 角色全部外部注入。
2. **写流多是「判断」不是「脚本」**：`curator` / `memory` 的写入是 agent 读 `SKILL.md` 做去重/冲突/去向判断的流程；落到脚本的只有确定性部分（`collections.py upsert/count`、`curate.py rm/reindex`、`doctor.py`、`gate.py`、`migrate.py`）。网关**不能简单"包脚本"了事**。
3. **skills-first + 防退化纵深**：operations 第一公民是 skill / 可直接跑的脚本；"协议是导航不是强制"——失效结果应是"可修复的漂移"，不是"污染正式状态"。

### 1.4 关键洞察：MCP 的分工天然契合 Substrate

MCP 的本分是 **server 提供"能力"、连接的 agent（LLM）提供"判断"**。映射到写知识：

- **判断由远端 agent 做**：它先用网关的 `search` / `read` 工具勘察，再决定去重 / contested / 去向。
- **机械部分由网关工具做**：按 frontmatter 落盘、校验 `≥2 wikilink`、更新索引、跑 doctor、`commit + push`。

**附带收获**：网关可把 **CONSTITUTION 摘要 + 目标 zone 的 Agent Packet 通过 MCP 的 tool description 与一个 `governance` resource 推给任何连进来的 agent** → **从没装过 skill 的远端 agent 也会被治理**。这解决了"远端 agent 没装 skill，治理规则怎么到它那"的根本问题，是本提案的核心价值之一。

---

## 2. 方案设计（架构）

### 2.1 新增 adapter 类别：`kind: gateway`

`adapters/README.md` 现定义两类 `kind`：

| 现有 kind | 含义 |
|---|---|
| `skill-runtime` | 引擎把 skill 装进该 runtime 的 skill 目录（claude-code / generic-filesystem / …） |
| `view-layer` | 只读视图，不装 skill（obsidian） |

MCP **两者都不是**：它既不往某 runtime 装 skill，也不是只读视图，而是**实例前面的访问/网关层**。故引入第三类：

| 新增 kind | 含义 |
|---|---|
| `gateway` | 在实例前面起一个协议服务（MCP），把引擎能力暴露给远程/本地的 agent；**不安装 skill** |

新增 `adapters/mcp/`（声明式 `adapter.yaml` + `README.md`，与现有 adapter 同构）。`substrate-sync` 见到 `kind: gateway` **一律跳过**（不当 skill 安装目标），与它现在拒 `view-layer` 的处理一致。

### 2.2 网关暴露的工具：分两档（YAGNI，首发只做最小集）

**A 档 — 确定性工具（直接包现有脚本，安全、机械）**

| MCP tool | 背后实现 | 读/写 |
|---|---|---|
| `substrate_search` | grep/glob over 实例（复用 doctor 的 wikilink/索引解析口径） | 读 |
| `substrate_read` | 读某页 / 列某 zone 的文件级索引 | 读 |
| `substrate_collection_add` | `collections.py upsert`（按 id 幂等去重） | 写 |
| `substrate_doctor` | `doctor.py`（体检 + 毕业阈值） | 读 |
| `substrate_intake` | `gate.py`（出安置建议 + 风险分级） | 读（判定） |

**B 档 —「勘察 + 受控写」工具（知识 / 记忆的机械化写入）**

- `substrate_write_page`：入参为结构化内容（`zone / title / body / tags / sources`）；server 做**确定性那半**——补全 frontmatter、校验 `≥2 wikilink`、更新 zone README 索引、跑 doctor 到 `0 ERROR`、`pull → commit → push`。**判断那半（去重 / contested / 去向）由连接的 agent 在调用前用 A 档读工具完成**。
- 写工具一律：先 `git pull` 再写；`--apply` 语义显式；失败回退不留脏状态。

> **`migrate` 不进网关**——它是引擎侧、需引擎仓库在场的操作，留作**主机侧管理任务**（见 §4 运维）。网关只暴露日常读写，不暴露跨版本迁移这种高风险动作。

### 2.3 触发机制与治理下发

**工具怎么被触发（与 skill 同源）**：MCP 工具是**模型自动调用**的——client 连上 server 后把工具清单（`name` + `description` + 入参 schema）注入模型上下文，模型拿用户意图去和各工具的 `description` 做匹配，命中就发调用。**这与 skill 的触发是同一套意图匹配**：skill 靠 `SKILL.md` 的 `description`，MCP 工具靠 tool 的 `description`，没有独立的"触发词字段"。**工程含义**：

- 每个 tool 的 `description` 直接**复用对应 `SKILL.md` 的触发词**（含多语言说法），触发率才稳。
- 工具集**保持小而清晰**：工具过多 / 描述含糊会让模型选错或漏调，且工具 schema **常驻上下文烧 token**（MCP 的"工具膨胀"是已知坑）。首发只上 §2.2 最小集。

**治理怎么随之下发**：

- **`instructions` 注入系统提示**：MCP server 初始化时返回的 `instructions` 字段会被 client 注入系统提示——用它声明"这是主人的 Substrate 实例；涉及笔记 / 记忆 / 收藏 / 待办用这些工具；写前先勘察并读 `substrate://governance`"。这是让治理**主动**生效的关键通道。
- **`substrate://governance` resource**（只读：`CONSTITUTION` 摘要 + 目标 zone 的 Agent Packet）：注意 **resource 默认不被模型自动触发**（不同于工具），所以不能只摆着——要靠上面的 `instructions` + 写工具 `description` 里硬性要求"调用前先读它"，治理才真落地。
- **Forbidden 守门**（密钥 / 凭据 / 敏感原文 / 大二进制永不入库）在 server 侧**再校验一遍**，不只靠远端 agent 自觉——纵深防御的一环。

### 2.4 两种部署形态

| 形态 | 传输 | 场景 | 复杂度 |
|---|---|---|---|
| **A — stdio 本地** | stdin/stdout | agent 把 server 当子进程拉起，操作本机实例副本 | 最低，**先用它验证全链路** |
| **B — 远程常驻** | streamable HTTP（含 SSE） | `<mcp-host>` 持唯一实例副本 + 跑 server；多机远程连同一端点，**无需各自 clone / 装 skill** | 需鉴权 + TLS |

### 2.5 混合部署（推荐的最终形态，正视单点故障）

网关是**叠加层不是替代层**：

- `<mcp-host>`：跑远程网关（给手机 / 轻量 agent 即插即用）+ 当 `migration_leader` 跑 doctor / 迁移。
- 主力开发机：仍 `git clone` 本地副本 + 装 skill（离线可用、Obsidian 直接编辑）。
- 二者都 `push` 到同一个私有 GitHub 实例仓库，自然合流。

→ 既拿到"集中、省事、手机能用"，又保留"本地、离线、可手翻"，**不把鸡蛋全押在主机一个篮子里**（主机挂了，主力机仍能离线工作）。

### 2.6 客户端接入与降级（取决于 runtime，不取决于模型）

**"能不能用网关"是 agent 的 runtime / harness 的属性，不是底层模型的属性。** 模型只负责 function-calling；真正去"连 server、拉工具清单、注入上下文、执行调用"的是包着模型的那层代码。所以接入前提是：

- 该 runtime **实现了 MCP client**（支持 stdio 与 / 或 streamable HTTP 传输）。具备的 runtime 零改造即可连；
- **连接是 client → server 出站**：client 主动拨向 `<mcp-host>`，**client 侧无需开入站端口**，NAT / 防火墙后亦可用。

**降级路径（与 skill-runtime 互补，不互斥）**：

- runtime **不是 MCP client** → 回退到现有 **skill-runtime adapter**（本地 clone + 装 skill，§1.1 的 git 分发式），或由其自有 harness 直接调网关的 HTTP 端点；
- 即网关（`kind: gateway`）与 skill-runtime 两条路**并存**：同一实例可同时被"装了 skill 的本地 runtime"和"连网关的远程 runtime"消费。

### 2.7 选型权衡：本地 skill 维护 vs MCP 网关

两条路都靠 `description` **自动触发**（见 §2.3），区别不在"自不自动"，而在 **活儿在哪跑、跨不跨网络边界**。供落地时按场景选：

| 维度 | A：本地 + skill | B：MCP 网关 |
|---|---|---|
| 单步 / 多步延迟 | 本地磁盘，快；仅 `pull/push` 走网络 | **每次 tool 调用一次网络往返**，多步流程累加 |
| 并发 / 一致性 | 各机各 clone，靠 git 解冲突；可能读到旧数据 | 单主机**串行化单写者**，client 间天然一致 |
| 可用性 / 离线 | 每机自洽、可离线、无单点 | 依赖主机 + 网络，**主机挂 = 远端失忆（单点）** |
| 数据暴露面 | **整库 clone 到每台设备** | 数据只在主机；远端只持 **scoped token**，不持全库 |
| 凭据爆炸半径 | 每台设备都有 git 写凭据 + 全量数据；某台失陷波及全库，已有 clone 收不回 | 远端只有可即时吊销的 scoped token，半径小 |
| 治理强度 | 靠每台装了 skill 并照做（自觉） | server 端 `instructions` + doctor 硬闸**集中强制**，绕不过 |
| 接入新 agent | 每台 clone + sync skill（N 台 N 次） | 指个端点 + 给 token（近零） |
| 上下文 token | 读 `SKILL.md` + 文件进上下文 | 工具 schema 常驻上下文；read 工具可只回切片 |
| 可观测 / 审计 | git history + 各机散落日志 | **中心审计**：每次调用谁 / 何工具 / 何时一处可查 |
| 能力面 | 全 shell + 文件，能干任何事（更猛也更险） | 只能调暴露的工具（更安全，但未暴露的远程做不了） |
| 额外成本 | 用现有机器，零额外 | 一台 24/7 主机（钱 + 运维） |

**结论**：要快 / 离线 / 全权且机器可信 → 倾向 A；要省事接入异构或受限设备、数据不落地到每台、集中审计与强制治理 → 倾向 B。二者可**混合**（§2.5）：受限 / 边缘设备走 B，主力机留 A。

---

## 3. 工程设计

### 3.1 协议实现：官方 MCP SDK（一个**受限、可选**的依赖例外）

网关用**官方 MCP SDK**实现 server（省去手写 JSON-RPC、跟随协议演进省心）。这是对引擎"零 pip 依赖"惯例的一次**刻意、受限的例外**，边界如下：

- **范围隔离**：依赖只存在于 `skills/substrate-mcp/`（gateway adapter 组件）。**引擎核心**——`doctor` / `sync` / `curate` / `collections` / `gate` / `migrate`——**仍是纯标准库、零安装**，红线不破。
- **显式声明**：在 `skills/substrate-mcp/SKILL.md` 的 manifest `dependencies` 字段声明（schema 已有此字段），缺失时**优雅降级**（报"未安装 MCP SDK，网关不可用"，不崩主流程）。
- **可选安装**：只有要起网关的用户才装；纯 git 分发式用户完全不受影响。
- **钉死协议版本**：server 启动时声明所支持的 MCP 协议版本与 capabilities；把"跟踪 MCP 协议演进"纳入引擎维护清单。

> 备注：若未来要彻底回到零依赖，可用 python3 标准库（stdio 走逐行 JSON-RPC、远程走 `http.server`）重写 server——接口不变，仅换实现。本提案不锁死这条退路。

### 3.2 文件落位（外科手术式，符合现有结构）

```
adapters/mcp/
├── adapter.yaml          # kind: gateway，声明 server 入口 / 传输 / 鉴权占位 / 暴露的工具
└── README.md             # 怎么起、怎么连、安全注意

skills/substrate-mcp/      # 网关 server（脚本即真相，无独立二进制）
├── SKILL.md              # manifest: target_runtimes:[all] / risk_level:high
│                         #   capabilities:[shell,network,write] → 按规则 = 人工 audit 级
└── server.py             # 官方 MCP SDK；stdio + 可选 http 传输；把工具映射到既有脚本

docs/proposals/mcp-adapter.md   # ← 本方案文档
```

- **复用**现有 `curate.py` / `collections.py` / `doctor.py` / `gate.py`，**不重写逻辑**，只在 `server.py` 里调它们 + 做 frontmatter / 索引的机械写。
- **小改 `sync.py`**：识别 `kind: gateway` 并跳过（防止被误当 skill-runtime 安装）。
- **`fleet/`**：主机在实例的 `fleet/` 里标 `role: mcp-host`（通常兼 `migration_leader`）——具体机器是实例数据，不进引擎。

### 3.3 `adapters/mcp/adapter.yaml` 字段草案（声明式）

```yaml
adapter: mcp
kind: gateway                 # 新增类别：既非 skill-runtime 也非 view-layer
runtime: mcp                  # 仅用于标识，不写进 skill 的 target_runtimes

server:
  entry: "skills/substrate-mcp/server.py"
  transports: [stdio, http]   # 首发 stdio；http 为远程常驻形态
  protocol_version: "<pin>"   # 钉死所支持的 MCP 协议版本
  instance: "${SUBSTRATE_INSTANCE}"   # 操作哪个实例（外部注入，引擎不假设）

auth:                         # 仅 http 形态需要；stdio 形态忽略
  method: bearer-token
  scopes: [read-only, read-write]     # 映射到 zone 的 readers/writers
  tokens_source: "本地配置（不入库）"

tools_exposed:                # 首发最小集（见 §2.2）
  - substrate_search          # 读
  - substrate_read            # 读
  - substrate_doctor          # 读
  - substrate_collection_add  # 写（collections.py upsert）
  # M2 起：substrate_write_page / substrate_intake / resource substrate://governance

local_state:
  audit_log: "${SUBSTRATE_INSTANCE}/.substrate/mcp-audit.log"
  committed: false            # execution-plane 本地状态，永不入库
```

### 3.4 安全（远程形态必须有）

- **鉴权**：每客户端一个 token；分 **read-only / read-write 两种 scope**，映射到 zone 的 `readers/writers`。`memory` 区 `privacy: sensitive`，默认更严。
- **审计**：每次 tool 调用落本地 audit log（谁 / 何工具 / 改了哪页）——本地状态，不入库（已在 `template/.gitignore` 思路内）。
- **纵深**：Forbidden 守门在 server 侧复校；写工具全程 `pull → 写 → doctor → commit → push`，**doctor 不过就拒绝提交**。
- **暴露面**：远程形态置于 TLS 之后；不在公网裸暴露；token 轮换。

---

## 4. 长期运维

1. **进程生命周期**：systemd unit 或容器常驻；崩溃自拉起。
2. **并发与一致性**：写操作**单写者串行化**（文件锁）；每次写 = `pull → 改 → commit → push`，push 冲突则 `pull --rebase` 重试——**把 git 当并发裁判**，杜绝多 agent 同时写撕裂。
3. **体检即运维**：cron 定时 `doctor.py`，有 `ERROR` 告警；同一套 doctor 兼作 CI（迁移前后跑同一套不变量）。
4. **升级**：引擎 bump 版本 → 在这台 `migration_leader` 上跑 `substrate-migrate`（git tag 快照 + 前后 doctor 校验）；其它机器 `pull` 看到版本已最新即跳过。**网关不自暴露 migrate**。
5. **备份**：git 全历史 + push 到私有 GitHub 即备份；`pre-migrate-<from>` tag 永远可回滚。
6. **单点故障（正视）**：主机挂 = 这些远端 agent 当场失忆。**缓解 = §2.5 混合部署**——主力机保留本地副本 + skill，网关是叠加层，所有写最终汇到同一 GitHub 实例仓库。
7. **协议演进**：把"跟踪 MCP 协议版本变化"纳入引擎维护清单；server 启动声明 capabilities 与协议版本；SDK 升级走常规依赖升级。
8. **无状态主机设计（关键）**：把网关当**可丢弃**的——**开机从 GitHub `clone` 实例工作副本，每次写即 `commit + push`**。于是临时文件系统的主机（容器 / PaaS，重启即重置）也不丢数据：**持久真相在 git remote，不在主机磁盘**。主机上唯一的本地状态是 audit log + token（不入库；token 走环境变量 / secret）。需要持久磁盘时才挂卷，多数场景无需。

### 4.1 主机部署与暴露形态（引擎中立）

网关是 client → server 出站连接，所以**主机要解决的只是"让 client 够得着"**。按"client 是否需额外接入"分几类，引擎不绑定任何具体产品：

| 形态 | 需公网 IP？ | client 需额外接入？ | 取舍 |
|---|---|---|---|
| **托管平台公网端点** | 否（平台给 HTTPS） | 否（拿 URL + token） | 最省网络配置；数据驻第三方 + 须配无状态（见上） |
| **自托管 + 公网 IP 直连** | 是（须真公网、最好静态；当心 CGNAT / 动态 IP） | 否 | 简单可达，但**暴露面最大**：须自管 TLS + 强 token + 防火墙 + 打补丁 |
| **反向隧道**（主机出站到隧道商） | 否 | 否（拿公网 URL + token） | 无公网 IP / 无端口转发 / TLS 托管；多依赖一个隧道商 |
| **mesh / overlay VPN** | 否 | **是**（client 须入同一私网） | 网络层隔离最强（仅自有设备可达 + ACL）；每个 client 要接入私网 |

**两条不变的原则**：

- **token 鉴权与网络层无关，始终要配**（纵深防御）：公网形态下它是唯一防线，私网形态下它是第二层——某台设备失陷不应自动拿到无 scope 权限。
- **信任边界**：主机持有实例工作副本 + 写 token；缓解靠"git remote 为持久真相源 + scoped token + 即时吊销"。是否接受数据驻于某主机，是部署者按自身信任模型的取舍，**不属引擎机制**。

---

## 5. 与现有契约的自洽核对

- **adapter 契约**：新增 `kind: gateway` 是对 `adapters/README.md` 两类 kind 的扩展；`sync.py` 跳过 gateway，与现有"拒 view-layer"一致。未来若 adapter 接口稳定，可补 `schemas/adapter.schema.yaml` 把三类 kind 入契约。
- **skill-manifest 契约**：`substrate-mcp` 用既有字段——`target_runtimes:[all]`、`risk_level:high`、`capabilities:[shell,network,write]`（按 §7 风险分级 = 人工 audit 级，**不能自动晋升**）、`dependencies` 声明 MCP SDK。
- **admission / 防退化**：网关写入复用 doctor 不变量校验，Forbidden 守门 server 侧复校，契合"协议失效 → 可修复漂移，不污染正式状态"。
- **Engine / Instance 分离**：server 不含任何用户偶然事实；实例路径 / 鉴权 / fleet 角色全外部注入。

---

## 6. 落地路线（分阶段，每阶段可验证）

| 里程碑 | 内容 | 验收 |
|---|---|---|
| **M1** | `kind: gateway` 接口 + `adapters/mcp/` + `sync.py` 跳过 gateway + **stdio 最小 server**（`search` / `read` / `doctor` / `collection_add` 四工具）+ 测试 | 一个 MCP client 经 stdio 连上，能搜/读/体检/加一行 collection，doctor 0 error |
| **M2** | `substrate_write_page`（知识 / 记忆受控写）+ resource `substrate://governance` + `instructions` 注入 + Forbidden 复校 | 远端 agent 不装 skill，仅凭网关写出一篇合规知识页（≥2 wikilink + 索引更新 + doctor 通过） |
| **M3** | 远程传输（streamable HTTP）+ token 鉴权 + read/write scope + 无状态主机设计（见 §4）+ 部署文档（暴露形态见 §4.1、`fleet` 角色） | 两台机器远程连同一 `<mcp-host>`，read-only token 写被拒、read-write token 写成功 |
| **M4** | 审计日志 + 并发串行化 + doctor cron + 混合部署指南 | 并发写不撕裂；审计可追溯；主机挂后主力机离线可用 |

---

## 7. 成败标准

不是"接了 MCP"，而是：**一个从没装过 skill 的远端 agent，能否经网关低成本读写同一份实例、且照样被宪法约束、写错能被 doctor 发现、绝不把密钥/脏数据塞进库、主机挂了也不丢东西。**
