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

### 2.3 治理随 MCP 下发

- 每个 tool 的 `description` 内嵌触发词与红线（取自对应 `SKILL.md` 的 `description` 字段）。
- 暴露只读 resource `substrate://governance`：吐 `CONSTITUTION` 摘要 + 目标 zone 的 Agent Packet。远端 agent **写前先读它** → 即便没装 skill 也守宪法。
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
| **M2** | `substrate_write_page`（知识 / 记忆受控写）+ resource `substrate://governance` + Forbidden 复校 | 远端 agent 不装 skill，仅凭网关写出一篇合规知识页（≥2 wikilink + 索引更新 + doctor 通过） |
| **M3** | 远程传输（streamable HTTP）+ token 鉴权 + read/write scope + 部署文档（systemd / 容器、TLS、`fleet` 角色） | 两台机器远程连同一 `<mcp-host>`，read-only token 写被拒、read-write token 写成功 |
| **M4** | 审计日志 + 并发串行化 + doctor cron + 混合部署指南 | 并发写不撕裂；审计可追溯；主机挂后主力机离线可用 |

---

## 7. 成败标准

不是"接了 MCP"，而是：**一个从没装过 skill 的远端 agent，能否经网关低成本读写同一份实例、且照样被宪法约束、写错能被 doctor 发现、绝不把密钥/脏数据塞进库、主机挂了也不丢东西。**
