# 提案：Substrate MCP 网关（adapter `kind: gateway`）

> **状态：DEFERRED（已设计，暂不落地）。** 这是一份经对抗式评审后**诚实化、缩小 scope** 的设计。
> 它**不含实现代码**；在下面的「触发条件」满足前，本仓库不实现它，只把它当一份停泊的设计停在分支上。
>
> **解除 DEFER 的两个触发条件（须同时满足）**：
> 1. **有一个你真实在跑的 agent，确实被「git clone + 装 skill」卡住**——不是设想中的手机端，而是一个具体的、今天就接不进来的 runtime。
> 2. **已有一个在真机上验证过的第二 skill-runtime**（codex 或 hermes）逼出了稳定的 adapter 接口。
>    —— 见 `BUILD-PLAN.md` P4：「先做 generic-filesystem + claude-code，等**第二个 runtime 真正逼出抽象**再扩」。网关是**第三类** adapter，绝不能成为「逼出 adapter 抽象」的那个；那必须由一个真实的 skill-runtime 来做。
>
> **定位**：设计 + 工程 + 运维方案，基于引擎 `ENGINE_VERSION = 0.3.0`。落地路线见 §6（前置先行、读优先、写与远程都 DEFER）。
> **关系**：扩展 `BUILD-PLAN.md` §15 P4（适配器）。
> **命名**：引擎 = Substrate；用户私有实例 = `<instance>`；常驻主机 = `<mcp-host>`（占位，不绑定任何具体机器）。

---

## 0. 一句话 + 唯一不可替代的价值

给 Substrate 加一个 **MCP 网关**：让能说 MCP 的 agent 远程连到同一份实例读写共享状态，无需各自 `git clone`、各自装 skill。

**但它唯一不可替代的价值只有一条**——其余（远程读、搜索、NAT 穿透、自动触发）更便宜的台阶都能给（见 §1.5）：

> **对一个从没装过 skill 的远端写者，在「agent 与仓库之间」做服务端治理强制**——frontmatter 校验、`≥2 wikilink`、doctor 必须 0 ERROR 才提交、Forbidden 服务端复校、回流 skill 强过 `gate.py` 风险分级。现成的 filesystem/git MCP server、raw git push、托管同步服务**都给不了这个**：它们让远端 agent 直接无中介地写，而宪法住在它从没装过的 skill 里，没有任何东西约束它。

整份提案是否值得建，**全押在「这条价值是否是硬需求」上**。如果不是，就用 §1.5 里更便宜的台阶。

---

## 1. 背景与动机

### 1.1 现状：git 分发式（去中心）

每台机器 `git clone` 实例 → `substrate-sync` 把维护 skill 装进该机 runtime → skill 操作**本地文件** → 机器间靠 `git pull/push` 同步。

- **优点**：离线可用、每台机自洽、无单点故障。
- **代价**：每台机 / 每个 agent 都要装一遍（clone + sync skill）；不会「装 skill」的 runtime 接不进来。

### 1.2 目标：再提供一种集中式接入（叠加，不替代）

一台常驻主机 `<mcp-host>` 持唯一一份实例工作副本 + 跑 MCP server；其它 agent 远程连同一端点。两种模型不互斥（§2.5 混合部署）。

> **诚实标注客户端现实**：MCP client 支持集中在**开发者 / agent harness**——Claude Code、Claude Desktop、Cursor、VS Code/Copilot、Cline、Zed，以及**你自己写的、内嵌 MCP client 的 agent**（如 Hermes 类 runtime）。**消费级手机 chat app 当「连任意自托管远程 server」的通用 MCP client，在 2026 基本不成立**（它们的 connector 是受策展的托管集成，不是「把我手机 agent 指向我自建的盒子」）。所以本提案**不**以「手机端即插即用」为动机；那是 UNVERIFIED 的设想，按引擎惯例标「声明，未在真机验证」，**绝不让它驱动远程里程碑(M3)的 scope**。真正的目标 client 是上面那串 harness + 你自己的嵌入式 agent。

### 1.3 三条必须遵守的项目约束（durable，原样保留）

1. **Engine / Instance 分离**：MCP server 是**引擎机制**，操作某个实例，但**不依赖任何用户偶然事实**——实例路径、鉴权、fleet 角色全部外部注入。
2. **写流多是「判断」不是「脚本」**：`curator` / `memory` 的写入是 agent 读 `SKILL.md` 做去重/冲突/去向判断的流程；落到脚本的只有确定性部分。网关**不能简单「包脚本」了事**。
3. **skills-first + 防退化纵深**：operations 第一公民是 skill / 可直接跑的脚本；「协议是导航不是强制」——失效结果应是「可修复的漂移」，不是「污染正式状态」。**注意：这条对连进来的远端 agent 同样成立**，所以治理不能靠「它会照做」，必须靠服务端硬闸（见 §2.3、§4）。

### 1.4 关键洞察：MCP 的分工契合 Substrate

MCP 的本分是 **server 提供「能力」、连接的 agent 提供「判断」**。映射到写知识：判断由远端 agent 做（先用读工具勘察，再决定去重/contested/去向），机械部分由网关工具做（按 frontmatter 落盘、校验、更新索引、跑 doctor、commit+push）。

> **重要的诚实化**：附带「把治理推给任何连进来的 agent」这个收获**是 best-effort，不是强制**——见 §2.3 对 `instructions` 的降级。真正的强制在服务端硬闸（doctor + Forbidden 复校 + gate.py），不在「agent 会读 governance 并照做」。

---

## 1.5 替代方案考量与取舍（评审要求的决定性对比）

> 一个 YAGNI-native 的项目必须先打掉更便宜的台阶，定制网关才有依据。下面把五个选项摆上台面，每个标「网关比它多买到什么」。

| 替代方案 | 今天就能用？ | 网关比它多买到什么 | 取舍 |
|---|---|---|---|
| **0. do-nothing（P4 null hypothesis）** | — | 在「触发条件」满足前，**什么都不缺** | **这是默认值**。live 实例今天只有一个 runtime（Claude Code），无任何 agent 被 clone 卡住 → 默认就该 defer。本提案必须先**击败**这一项才动手 |
| **1. 现成 filesystem/git MCP server 指向实例 clone** | 是（零构建） | **服务端治理强制**（doctor/Forbidden/admission）。现成 server 只暴露读写原语，skill-less agent 能写任何垃圾、塞密钥、破坏索引 | 对「远程读 + 受治理的 markdown 写」的**大头用例，它零成本拿到 ~80%**。被拒**当且仅当** §0 那条价值是硬需求——否则首选它 |
| **2. 薄 REST/HTTP 端点 + 一个小 skill（无 MCP SDK）** | 近乎（几十行） | 同样的治理 choke point，**但少了 MCP 的「描述自动触发」**（要 agent 主动调端点） | §2.6 自己承认「非 MCP harness 可直接调 HTTP 端点」→ **MCP 协议本身不是 load-bearing，治理 choke point 才是**。见 §3.4 的「plain-HTTP 核心 + MCP 薄壳」抉择 |
| **3. raw git-over-HTTPS（远端 agent 直接 pull/push 私有仓库）** | 是（零代码） | 治理强制 + 可即时吊销的 scoped token + 中心审计 + 单写者串行化 | §4 的无状态主机其实**就是靠它**（git remote 为持久真相）。网关相对它的**全部 delta = 这四样**。值不值，看你要不要这四样 |
| **4. 托管同步服务** | 是 | 自托管、无第三方数据驻留、无 vendor lock | 按引擎红线**直接拒**（数据驻第三方、锁平台、与自托管 git 精神冲突）——但要**明写一行**，不是默默略过 |

**结论**：网关的不可替代理由**收敛为 §0 那一条**。传输 / NAT / 读 / 搜索全可由更便宜的台阶提供。所以——**先用「do-nothing」直到 §0 的硬需求被一个真实 agent 逼出来**；真要建，**核心可做成 plain-HTTP 强制 API（零依赖红线不破），MCP 只当上面一层可选的自动调用薄壳**（§3.4）。

---

## 2. 方案设计（架构）

### 2.1 新增 adapter 类别：`kind: gateway`（实验性、不版本化）

`adapters/README.md` 现定义两类 `kind`：`skill-runtime`（装 skill）与 `view-layer`（只读视图，不装 skill，如 obsidian）。MCP 两者都不是，是**实例前面的访问/网关层**，故引入第三类 `gateway`（不安装 skill）。

> **诚实化两点**：
> - **现状代码并未「干净跳过」gateway**：`sync.py` 的 `adapter_target()` 今天**只**特判 `kind=='view-layer'`（line 92）；一个没有 `skill_install.target` 的 gateway adapter 会落到通用错误「未声明 skill_install.target」。所以 M1 必须**新增**一个 gateway 早退分支（镜像 view-layer 那条），不是「已经一致」。
> - **adapter 接口尚未定稿**（`adapters/README.md:22`），且**还没有第二个真机验证过的 skill-runtime**。所以 `gateway` 先当**实验性、不版本化**的 kind，**在 stdio M1 真跑通前不碰 `schemas/`**（不写 `adapter.schema.yaml`）。把 `adapter.schema.yaml` 留给「第二个真实 runtime 逼出抽象」时一起做（见 §3.2、引擎地基 §6 M0）。

### 2.2 网关暴露的工具：极小起步（读优先）

**M1 真正的最小探针 = 一个只读工具**，用来回答唯一的核心问题「MCP client 经这条通道拿到的 context，够不够它有用地驱动这份实例」。在这个答案出来前，不加写路径、不加确定性包装。

**首发（M1，只读、stdio）**

| MCP tool | 背后实现 | 读/写 |
|---|---|---|
| `substrate_read` | 读某页 / 列某 zone 的文件级索引 | 读 |
| `substrate_search`（可第二步加） | grep/glob over 实例（复用 doctor 的 wikilink/索引解析口径） | 读 |

**受控写（DEFERRED 到 M2，且有硬前置）**

- `substrate_write_page`：入参为结构化内容（`zone/title/body/tags/sources`）；server 做确定性那半（补 frontmatter、校验 `≥2 wikilink`、更新 zone README 索引、跑 doctor 到 0 ERROR、`pull→commit→push`）。判断那半（去重/contested/去向）由连接 agent 在调用前用读工具完成。
- **写工具有两个不可绕过的前置**（见 §6 M0、§4.1）：① 服务端**确定性 Forbidden/secret 扫描器**（拒绝而非 flag）+ doctor secret ERROR 检查存在；② 网关自己的 **deny-by-default authz 层**存在。**两者不全 → 不暴露任何写工具（连 stdio 都不）**。
- **去重从「行为」改「结构」**（协议无法强制 agent 先读再写）：`substrate_write_page` 命中疑似重复时**返回候选项 + 要求显式 `confirm_after_review` 再写**，而不是指望 agent 自觉先勘察。

> **`migrate` 永不进网关**——高风险、需引擎仓库在场，留作主机侧 / `migration_leader` 管理任务（§4.2）。

### 2.3 触发机制与治理下发（`instructions` 已降级为 advisory）

**工具怎么被触发**：MCP 工具是模型自动调用的——client 把工具清单（`name`+`description`+入参 schema）注入模型上下文，模型拿用户意图和各工具 `description` 匹配。**与 skill 触发同源**（靠 `description`，无独立触发词字段）。工程含义：复用对应 `SKILL.md` 的触发词（含多语言）；工具集保持小而清晰（tool schema 常驻上下文烧 token，是 MCP 已知的「工具膨胀」坑）。

> **触发可靠性是 client-dependent 的**：不同 client 会截断/改写 description、要手动开关工具、或给工具名加命名空间前缀（如 `mcp__substrate__write_page`，会改变匹配）。**别假设与 skill 触发等价**——M1 验收必须**点名一个具体 client**（如经 Claude Code 或 MCP Inspector 走 stdio）逐个验。

**治理怎么随之下发**（强制 vs 提示，分清）：

- **服务端硬闸（真正的强制，load-bearing）**：写工具全程 `pull → 写 → doctor(必须 0 ERROR) → commit → push`，doctor 不过就拒绝提交；Forbidden **服务端确定性复校**（§4.1）；回流 skill 强过 `gate.py`。**治理靠这些，不靠 agent 自觉。**
- **`instructions`（best-effort 提示，NOT 强制）**：MCP 规范把 server 的 `instructions` 字段标为 **"Optional instructions for the client"**——**client MAY 注入系统提示，也 MAY 忽略**。真实 client 行为高度不一致（有的 prepend、有的只摆在 server-info 面板模型看不到、有的丢弃、有的只首次连接生效）。所以「连个没装 skill 的 agent 它就被治理」**只对「注入 instructions 且模型服从」的那个子集成立**。→ **把 `instructions` 当锦上添花的提示，强制语言全部移到服务端硬闸。**
- **治理摘要直接嵌进每个写工具的 `description` 与其拒绝 payload**——不指望 agent 先读了 `substrate://governance` resource（见下）。
- **`substrate://governance` resource**（只读：CONSTITUTION 摘要 + 目标 zone 的 Agent Packet）：**resource 默认不被模型自动触发**（规范：application-driven，由 host 决定是否纳入 context）。所以它只是补充，不能是治理落地的依赖。

### 2.4 两种部署形态

| 形态 | 传输 | 场景 | 状态 |
|---|---|---|---|
| **A — stdio 本地** | stdin/stdout | agent 把 server 当子进程拉起，操作本机实例副本 | **M1：先用它验证全链路** |
| **B — 远程常驻** | **Streamable HTTP**（单端点，可经 SSE 流式回包） | 多机远程连同一端点 | **DEFERRED（M3）**，需鉴权 + TLS |

> **传输措辞修正**：远程传输是 **Streamable HTTP**（2025-03-26 规范）。**老的独立 HTTP+SSE 传输（2024-11-05）已弃用，不要实现它。** adapter.yaml 的 `transports` 写 `[stdio]`（M1），http 留到 M3。

### 2.5 混合部署（最终形态，正视单点故障）

网关是**叠加层不是替代层**：`<mcp-host>` 跑远程网关 + 当 `migration_leader`；主力开发机仍 `git clone` 本地副本 + 装 skill（离线、Obsidian 直接编辑）；二者都 push 到同一私有 GitHub 实例仓库自然合流。主机挂了主力机仍能离线工作。

> **诚实化并发**：file lock 只串行化**单主机**上的写者；这个 hybrid 拓扑里，本地机直接 push 到同一 remote，**会重新引入 file lock 管不到的 git 级并发**——所以**不能**宣称 hybrid 下「client 间天然一致」。跨写者冲突由 git 调和，且必须降级为 **doctor 可检测的可修复漂移，绝不静默覆盖**（见 §4.1）。

### 2.6 客户端接入与降级

「能不能用网关」是 agent 的 **runtime/harness 属性，不是模型属性**：模型只负责 function-calling；连 server、拉工具清单、注入上下文、执行调用的是包着模型的那层代码。所以接入前提是该 runtime 实现了 MCP client；连接是 **client → server 出站**（client 主动拨向 `<mcp-host>`，client 侧无需开入站端口，NAT/防火墙后亦可用）。

**降级路径**：runtime 不是 MCP client → 回退到 skill-runtime adapter（本地 clone+装 skill），**或由其 harness 直接调网关的 plain-HTTP 端点**（§3.4）——后者正说明 MCP 协议不是 load-bearing。

### 2.7 选型权衡：本地 skill 维护 vs MCP 网关（durable，原样保留——全文最有价值的产物）

| 维度 | A：本地 + skill | B：MCP 网关 |
|---|---|---|
| 单步 / 多步延迟 | 本地磁盘，快；仅 pull/push 走网络 | 每次 tool 调用一次网络往返，多步累加 |
| 并发 / 一致性 | 各机各 clone，靠 git 解冲突；可能读到旧数据 | 单主机串行化单写者，**但 hybrid 下仍有 git 级并发（见 §2.5）** |
| 可用性 / 离线 | 每机自洽、可离线、无单点 | 依赖主机 + 网络，主机挂 = 远端失忆（单点） |
| 数据暴露面 | 整库 clone 到每台设备 | 数据只在主机；远端只持 scoped token |
| 凭据爆炸半径 | 每台设备都有写凭据 + 全量数据 | 远端只有可吊销的 scoped token（**前提是 token store 真存在，见 §4.1**） |
| 治理强度 | 靠每台装了 skill 并照做（自觉） | server 端 doctor 硬闸 + Forbidden 复校**集中强制**，绕不过 |
| 接入新 agent | 每台 clone + sync skill（N 台 N 次） | 指个端点 + 给 token（近零） |
| 上下文 token | 读 SKILL.md + 文件进上下文 | 工具 schema 常驻上下文；read 工具可只回切片 |
| 可观测 / 审计 | git history + 各机散落日志 | 中心审计（**前提是审计持久且防篡改，见 §4.1**） |
| 能力面 | 全 shell + 文件，能干任何事（更猛也更险） | 只能调暴露的工具（更安全，但未暴露的做不了） |
| 额外成本 | 用现有机器，零额外 | 一台 24/7 主机 + **永久跟踪 MCP 协议演进**的维护税 |

**结论**：要快/离线/全权且机器可信 → A；要省事接入受限设备、数据不落地到每台、集中审计与强制治理 → B。二者可混合（§2.5）。

### 2.8 写回与回流（记忆 / skill）经网关

- **记忆写回**：经 `substrate_write_page` 落 `memory/` 区。判断由 client 做；**机械写 + Forbidden 复校 + doctor + push** 由网关做。**前置同 §2.2 写工具**（Forbidden 扫描器 + authz 层）。
- **skill 回流**：暴露「提交 skill」工具，把 skill 存进 `skills/_incoming/` 隔离区，并在**服务端跑 `gate.py` 风险分级**：只读写 markdown 可自动晋升，凡含 shell/network/secrets/modify-* 一律留隔离区转人工 audit。**红线：绝不自动把任意 skill 变成可调工具**——那等于让远端 agent 给自己开可执行能力。

### 2.9 agent 怎么获得 skill（两条分发路径）

- **会装 skill 的 runtime** → 既有 `substrate-sync`。
- **MCP-only 的 agent** → 不「装」：① 纯做法类 skill（markdown、只读写）→ 用 `substrate_read` **读那篇 SKILL.md 照做**（零安装，多数参考 skill 属此类——**这正是「现成 fs MCP server + 读端点」就能覆盖大头的原因，见 §1.5**）；② 需确定性脚本的 → 有意加进 `tools_exposed` 白名单；③ 实在要即时能力 → 退回 skill-runtime 安装。
- **红线：绝不自动把任意 skill 变成可调工具。** 「得手动进白名单」不是缺陷，是准入的延续。

---

## 3. 工程设计

### 3.1 协议实现：官方 MCP SDK（受限、可选的依赖例外）

网关用官方 MCP SDK 实现 server。这是对引擎「零 pip 依赖」惯例的**刻意、受限**例外：

- **范围隔离**：依赖只存在于 `skills/substrate-mcp/`。**引擎核心**（doctor/sync/curate/collections/gate/migrate）**仍纯标准库、零安装**。
- **显式声明 + 优雅降级**：在 `SKILL.md` manifest 的 `dependencies` 字段声明。**⚠️ 现状：没有任何代码读 `dependencies`**（schema 有该字段但零消费者）——所以「缺失时优雅降级」**必须真写出来，不能假设它已存在**。M2 验收须有一个测试：MCP SDK 缺失 → server 导入失败产出「未安装 MCP SDK，网关不可用」，且**不破坏任何引擎核心脚本的调用**。
- **可选安装**：只有要起网关的用户才装。
- **钉死协议版本**：server 启动声明所支持的 MCP 协议版本与 capabilities；把「跟踪 MCP 协议演进」纳入引擎维护清单（这是网关带来的**永久维护税**，alternatives 没有）。

### 3.2 文件落位（外科手术式）

```
adapters/mcp/
├── adapter.yaml          # kind: gateway（实验性）；server 入口/传输/鉴权占位/暴露工具
└── README.md             # 怎么起、怎么连、安全注意

skills/substrate-mcp/      # 网关 server
├── SKILL.md              # manifest: target_runtimes:[all] / capabilities:[shell,network,write]
│                         #   → gate.py 实算 = audit 级，不能自动晋升（正确）
└── server.py             # MCP SDK；M1 仅 stdio + 只读工具；调既有脚本 + 机械写

docs/proposals/mcp-adapter.md   # ← 本方案文档
```

- **复用现有 `curate.py` / `collections.py` / `doctor.py` / `gate.py`，不重写逻辑。**
- **小改 `sync.py`**：新增 `kind: gateway` 早退跳过分支（§2.1）。
- **不碰 `schemas/`**：`adapter.schema.yaml` DEFER 到第二个真实 runtime 逼出抽象时再写。

> **写工具的硬前置（不是 afterthought，是 M2 前的独立里程碑）**：`curate.py` 当前公开面是 `rm/reindex`，「建页+补 frontmatter+更新索引」那半的机械逻辑现在在 `substrate-curator` 的 SKILL.md 驱动流程里，**未必是可调用函数**。若 `server.py` 自行重实现，会出现**两条会漂移的确定性写路径**。→ **M2 前必须先把 `curate.py` 的机械写重构成可复用入口**，让 `substrate-curator` 与 `server.py` 都调它；并加测试断言两者对同一输入产出**字节相同**的 frontmatter/索引。

### 3.3 `adapters/mcp/adapter.yaml` 字段草案（声明式，M1 仅需 stdio+读部分）

```yaml
adapter: mcp
kind: gateway                 # 实验性：在 stdio M1 跑通前不进 schema
runtime: mcp
server:
  entry: "skills/substrate-mcp/server.py"
  transports: [stdio]         # M1 仅 stdio；http 留到 M3（DEFERRED）
  protocol_version: "<pin>"
  instance: "${SUBSTRATE_INSTANCE}"   # 外部注入
tools_exposed:                # M1 最小集（只读）
  - substrate_read
  # 第二步: substrate_search
  # M2(DEFERRED, 有前置): substrate_write_page / resource substrate://governance
# auth / local_state(audit) / 远程相关字段: 留到 M3/M4（见 §4，DEFERRED）
```

### 3.4 抉择：plain-HTTP 核心 + MCP 薄壳（解决「MCP 不是 load-bearing」）

§2.6 已承认「非 MCP harness 可直接调 HTTP 端点」，§1.5 表 2 说明**治理 choke point 才是核心，MCP 协议不是**。两条路二选一，**落地时显式决定**：

- **(a) 推荐方向**：把**确定性强制逻辑做成一个 plain-HTTP API**（标准库 `http.server` 即可，**核心零依赖、红线不破**），MCP server 只是**上面一层薄壳**，把 MCP 工具调用翻译成对该 API 的调用。好处：核心不背 SDK 依赖；非 MCP harness 直接用 HTTP；MCP 只为「MCP-native client 里的自动触发」这一便利付费。
- **(b) 备选**：直接用 MCP SDK 实现，**但必须明确论证**「MCP 的描述自动调用」值得让 SDK 成为网关路径的硬依赖。

---

## 4. 长期运维（M3/M4，DEFERRED——以下为「真要做远程时」的诚实清单，非现在的设计承诺）

> 评审共识：§4 的远程访问层（HTTP/token/scope/无状态主机/TLS/隧道矩阵/并发/版本闸）是**生产级多租户访问层**，在 stdio M1 证明核心价值前**不该详细设计**——大多决定会被 M1 教训推翻。故本节**压缩为「真要做时必须解决的硬问题清单」**，不再展开为方案。

### 4.1 真要做远程写，必须先解决的硬问题（每条都是 blocker）

1. **Forbidden 服务端复校没有机械实现可依靠**（blocker）：引擎里**没有任何 secret/Forbidden 检测器**——doctor 零 secret 扫描；唯一检测在 `import.py` 且只 flag-as-REVIEW 不阻断、漏裸 token/PEM/base64。威胁模型恰是「不肯自觉的远端 agent」：它能把私钥写进 `memory/`，doctor 查 frontmatter/wikilink 但**不查 secret**，0 ERROR 放行并 push → **「密钥永不进库」红线被破**。→ 必须先有**确定性 secret 扫描器（PEM/JWT/云密钥前缀 + 熵；拒绝而非 flag）+ doctor secret ERROR 检查**。两者不全 → 任何写工具**连 stdio 都不暴露**。
2. **scope→zone `readers/writers` 映射不成立**（major）：schema 自己说 readers/writers 是**约定不是闸门**，且 template 每 zone ship `[all]`（含 `memory: sensitive`）→ read-only token 仍映射 [all]、read-write 默认能写 sensitive memory。→ 网关须自带**独立 authz 层**：deny-by-default；read-only = 完全无写工具；read-write = 显式 zone allowlist **排除 privacy:sensitive**（除非单独授予 sensitive-write scope）。**明说这是网关强制，不继承 zone 声明。**
3. **并发不能用 `git pull --rebase` 当裁判**（major）：rebase 撞 zone README index / CSV 同一行 → 要么 abort（写静默丢）要么 `-X theirs/ours`（静默丢一方），且 doctor md-count 守卫**抓不到**（计数没变、内容被覆盖）。→ 改 **app 层乐观并发**：网关记下读取时的 base commit，push 冲突就 **abort + 重 pull + 经 client 重跑去重/去向判断**，**绝不 auto-merge** README/CSV。加并发测试：两写者抢同一 index 行，结局必须是「两个都在」或「一个被显式拒绝」，**绝不一个被静默覆盖**。
4. **不能在 push 落地前 ACK 写成功**（major）：commit 与 push 之间崩溃 → 下次 re-clone 静默丢弃未 push 的 commit → 「成功」ACK 是谎。→ **push 落地是写工具返回成功的前置条件**。
5. **审计日志必须持久 + 防篡改**（major）：gitignore 的本地 `*.log` 在临时主机上回收即丢、失陷可篡改 → 「中心防篡改审计」卖点底座最弱。→ ship 到 append-only 外部 sink，或 commit 一份脱敏审计到专用分支；本地 log 仅当缓存。
6. **版本闸要精确**（minor）：`parse_version` 对损坏/缺失输入返回 None。→ None / 缺失 / 任一方向 skew **都 latch 成只读**（gateway 旧 与 instance 旧 对称处理）；latch 须**显式人工清除**（重部署后），**不每请求重评**——避免迁移中途 flapping 丢失进行中的多步写。
7. **token store + 吊销路径要落地**（minor）：「可即时吊销的 scoped token」需要一个**活过主机回收**的 token registry，但 repo 不能存 token、无状态主机开机 re-clone。→ 指定外部 secret manager / KV，**每请求对它校验吊销**；否则 §2.7 的「小爆炸半径」站不住。

### 4.2 其余运维要点（真要做时）

进程生命周期（systemd/容器常驻、崩溃自拉起）· 体检即运维（cron doctor，ERROR 告警，同套 doctor 兼 CI）· **升级**：引擎 bump → 在 `migration_leader` 上 `--refresh` + `substrate-migrate`（git tag 快照 + 前后 doctor 校验），网关**重部署钉到新引擎版本**，其它机 pull 见版本最新即跳过；**网关不自暴露 migrate** · **无状态主机**：开机从 git remote re-clone，每次写即 commit+push，持久真相在 remote 不在主机磁盘 · **网关启动版本闸门**：网关引擎版本 ≢ 实例 `SUBSTRATE_VERSION` → fail-closed 只读（§4.1.6）· 暴露形态（托管端点 / 公网 IP / 反向隧道 / mesh VPN）引擎中立，**token 鉴权与网络层无关、始终要配**（纵深防御）。

---

## 5. 与现有契约的自洽核对

- **adapter 契约**：`kind: gateway` 是对两类 kind 的扩展，**实验性、不进 schema**（直到第二个真实 runtime 逼出抽象）。`sync.py` **需新增**跳过分支（不是「已一致」，§2.1 已更正）。
- **skill-manifest 契约**：`substrate-mcp` 用 `target_runtimes:[all]` / `capabilities:[shell,network,write]`（gate.py 实算 = audit 级，不能自动晋升，正确）。`dependencies` 字段**目前零消费者**，优雅降级**须实现**（§3.1）。
- **admission / 防退化**：网关写入复用 doctor 不变量校验；**但 Forbidden 服务端复校所需的 secret 检测器目前不存在**（§4.1.1），是写工具的硬前置。
- **Engine / Instance 分离**：server 不含任何用户偶然事实；实例路径/鉴权/fleet 角色全外部注入。✅

---

## 6. 落地路线（前置先行 · 读优先 · 写与远程 DEFER）

> **总原则**：先补「网关其实是引擎当前缺口」的地基（M0），再做一个极小只读 spike（M1）验证唯一新颖主张，**M2/M3/M4 全部 gated，须满足各自前置 + §0 的真实需求被逼出**。

| 里程碑 | 内容 | 门槛 / 验收 |
|---|---|---|
| **M0 — 引擎地基（独立有价值，非 MCP 专属）** | ① 确定性 Forbidden/secret 扫描器（拒绝级）+ doctor secret ERROR 检查；② zone 访问控制强制（write 脚本共用 scope helper，sensitive 默认更严）；③ `curate.py` 机械写重构成可复用入口 + 字节相同测试；④ 判断/写入半边补测（collections.upsert 幂等、curator add 冒烟）。**这些就是下一步「补引擎地基」的活，与 MCP 解耦。** | 各自有测试；doctor 能 ERROR 出密钥；scope helper 拦住越权写 |
| **M1 — stdio 只读 spike** | `kind: gateway` 实验性接口 + `adapters/mcp/`（仅 stdio+read）+ `sync.py` gateway 跳过分支 + **一个只读工具 `substrate_read`** + 针对**一个具体 client**（Claude Code 或 MCP Inspector）的验收 | 该 client 经 stdio 连上，能读一页 / 列一个 zone 索引；**回答「context 够不够有用」这一个问题**。不含任何写 |
| **M2 — 受控写（DEFERRED，前置：M0①②③ 全绿）** | `substrate_write_page`（结构化去重→返回候选+confirm 才写）+ Forbidden 服务端复校（用 M0① 的扫描器）+ resource `substrate://governance` + 治理摘要嵌进工具 description + MCP SDK 缺失优雅降级测试 + 「未先读治理也安全」测试 | 远端 agent 不装 skill，仅凭网关写出一篇合规知识页（≥2 wikilink + 索引更新 + doctor 0）；塞密钥被**拒绝**；高风险 skill 滞留 `_incoming` |
| **M3 — 远程（DEFERRED，前置：§0 被真实 agent 逼出 + M2 绿）** | Streamable HTTP + token 鉴权 + **独立 authz 层**（§4.1.2）+ token store/吊销（§4.1.7）+ 无状态主机 | 两机远程连同一 `<mcp-host>`，read-only token 写被拒、read-write 写成功且 sensitive 默认拒 |
| **M4 — 运维加固（DEFERRED）** | app 层乐观并发（§4.1.3）+ push-后-ACK（§4.1.4）+ 持久防篡改审计（§4.1.5）+ 版本闸 latch（§4.1.6）+ 混合部署指南 | 并发抢同一 index 行不静默覆盖；崩溃不谎报成功；引擎/实例版本错位 fail-closed 只读 |

---

## 7. 成败标准

不是「接了 MCP」，而是：**一个从没装过 skill 的远端 agent，能否经网关低成本读写同一份实例、且照样被服务端硬闸约束（doctor + Forbidden 复校 + gate.py，不靠它自觉）、写错能被 doctor 发现、绝不把密钥/脏数据塞进库、主机挂了也不丢东西。**

而在那之前——**§0 的硬需求被一个你真实在跑的 agent 逼出来之前，正确答案是 do-nothing（§1.5）。** 本提案停泊于此，等触发条件。
