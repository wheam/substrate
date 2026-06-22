---
name: substrate-intake
description: "Decide whether a new item should enter the repo, which zone, and whether it should become a skill (admission classifier + auto-reflow gatekeeper). Use when the user asks 'should I save this / where does it go / is this knowledge or a skill'. 中文触发：「这个要不要存 / 存哪 / 这算知识还是 skill / 该不该进库」。"
target_runtimes: [all]
risk_level: medium
capabilities: [shell]
reason: 内容分类器 + 自动回流 skill 守门（只读判定：跑确定性脚本，不改内容）
---

# substrate-intake — 内容分类器 + 回流守门

一个 **Substrate 实例**的准入判定器。两张脸，同一套 `governance/admission.md`：

1. **内容分类器**：人/agent 丢进来的新内容，出**安置建议**——进不进库、什么去向、落哪 zone、该不该拆成 skill、剔哪些敏感位。
2. **回流守门**：agent 自总结的 skill 自动落 `skills/_incoming/`，本 skill 判它能否**自动晋升**还是**转人工 audit**。

> 本 skill 只**判定与建议**，不替你写内容、不替你晋升 skill——执行交 `substrate-curator`（写内容页）/ 人（晋升 skill）。
> 「调用本 skill 的脚本」= `python3 <本 skill 目录>/gate.py …`（无独立 CLI 二进制）。

## 何时用

- 用户丢来一段内容/一个文件/一段对话产物，问「这个要不要存 / 存哪 / 怎么存」。
- `substrate-import` 批量搬入时，对每条调本分类器。
- 有 skill 回流进 `skills/_incoming/`，要决定能不能自动晋升。
- 任何「写入前的去向判定」。

---

## 脸 ① 内容分类器

判一条新内容怎么安置，按顺序走：

### 第 1 步：入库四问（皆「是」才考虑进库）

1. **持久？** 长期有用，还是一次性/临时？
2. **属于个人 context？** 关于你/你的知识/你的事，还是公共信息随手可查？
3. **可文件化且适合 git？** 能落成文本/结构化文件、diff 友好？
4. **跨 agent 有共享价值？** 别的 agent/设备会需要它？

四问有「否」→ 多半不进库（Local-only 或干脆不存）。

### 第 2 步：定入库去向（admission outcome，四选一）

> 这是**单条内容**的准入去向（页/条目级），别和 zone 级的 `disposition` 字段（`zones.md` 里整个 zone 的存储取向，只 `{canonical, reference}`）混淆。

| 去向 | 何时 | 怎么做 |
|---|---|---|
| **Canonical** | 持久、个人、可文件化、跨 agent 有值的事实 | 进库成事实源（知识页/收藏行/共享记忆） |
| **Reference** | 多媒体、外部长文、PDF——本体大或非文本 | **只存引用 + 摘要 + 文字代理**（转写/OCR/描述/标签），本体不进库 |
| **Local-only** | 只对本机有意义（本地清单/缓存/身份/设备私配） | 不入库 |
| **Forbidden** | 密钥/凭据/敏感原文/大二进制 | **永不进库**——先剔除，再判其余部分 |

> **先剔敏感位再判其余**：一条内容里混了密钥/凭据 → 把 Forbidden 部分剥掉，剩下的再走四问。
> **多媒体 = Reference，库不是云盘**：agent 操作文字代理，不碰字节；小图可 git-lfs。

### 第 3 步：知识 vs skill（拆不拆 skill 的尺）

- 想**读**它 = 知识 → 走内容路由（下一步）。
- 想让 agent **反复做**它 = skill → 这不是知识页，应拆成 skill（写到 `skills/_incoming/` 走脸 ②）。

### 第 4 步：zone 路由 + zone vs page

- 落哪个 zone：按 `governance/zones.md` 的注册表（id/path/schema/maintainer_skill）。
- **zone vs page**：仅当有**独立 schema + 独立维护行为 + 独立访问模式**才开新顶层 zone；否则是已有 zone 的**一页/一行**。开新 zone 走 `CONSTITUTION.md` 的「新增类型 procedure」。

### 第 5 步：三层去重（**先查后写**，相似就合并不新建）

1. **精确键**：同名/同 slug/同 id？
2. **语义**：讲的是不是同一件事？
3. **结构**：该并进某已有页的一节，而非新建？

→ 命中任一层 = **合并进已有页**，不新建（这是 `CONSTITUTION` 不变量「绝不重复建页」的落地）。

### 输出（给调用者/用户的建议）

一条内容判完，给：**去向** + **落点（zone + 新页/并入哪页）** + **要剔的敏感位** + **是否应改拆 skill** + **去重命中情况**。
判定完交 `substrate-curator` 落地（本 skill 不自己写）。

---

## 脸 ② 回流 skill 守门

agent 自总结的 skill 自动落 `skills/_incoming/<skill>/`。是**可执行内容**，先隔离，过守门才晋升。

> 注：守门只针对**回流进 `_incoming/` 的 skill**。引擎自带的参考 skill（`substrate-*`）随仓库直接分发、由 `substrate-sync` 安装，**不经此闸门**（它们多含 `[shell]`，跑 gate 会判 AUDIT——那正是 fail-closed 的预期，不代表它们不可用）。

### 铁律：不信任自报 risk_level

风险**只由 `capabilities` 重推**，不看 SKILL.md 里自报的 `risk_level`。理由：自报值可被低报/写错；守门必须 **fail-closed**——拿不准就 audit，绝不误放危险件。

### 判法（确定性，用脚本）

```
python3 <本 skill 目录>/gate.py <skills/_incoming/某 skill 文件夹>
```

`gate.py` 读该 skill 的 `SKILL.md` frontmatter（容忍 BOM/前导空行/行尾注释），按 `capabilities`：

| 决策 | 条件 | 退出码 |
|---|---|---|
| **PROMOTE**（自动晋升） | **显式声明**了 capabilities（`capabilities: []` 或全在安全白名单内），且**无**危险/未知能力 | 0 |
| **AUDIT**（转人工） | `capabilities` 含 `shell`/`system`/`network`/`install`/`secrets`/`modify-skills`/`modify-governance` **任一**或白名单外未知能力；**或** capabilities **未声明 / 无法可靠解析**（标量、键重复、块内夹非列表项行、写了键却无项等都 fail-closed）。列表项间夹**空行/注释**是合法 YAML，会被**完整收集**不截断（杜绝旧 bug：截断丢掉后续 `- shell` 而误晋升） | 1 |
| **ERROR**（无法判，转人工） | 缺文件夹 / 缺 `SKILL.md` / 缺 frontmatter / 缺 `name` | 2 |

> **fail-closed**：未知 capability、以及「capabilities 未声明或解析不出」都倒向 audit——拿不准 = 人来看。要自动晋升，skill 必须**显式**写 `capabilities: []`（无危险能力）或只列安全能力。
> 退出码区分：闸门用 `!= 0` 判「不能自动晋升」，别只判 `== 1`（`2` 也是不放行）。

### 决策后做什么（本 skill 只判，执行交人/curator）

- **PROMOTE**：建议把该 skill 从 `_incoming/` 移到 `skills/<name>/`，补齐 manifest、跑 `substrate-doctor` 自检，再由维护流程提交。
- **AUDIT / ERROR**：**留在 `_incoming/`**，标记待人工复核；人确认安全（或改造降权）后才手动晋升。**不静默删、不静默放行。**

---

## 防御纵深里的位置

预防（入口走 skill）→ 检测（doctor）→ **隔离（本 skill：危险写入/危险回流挡在 `_incoming`/Forbidden 外）** → 纠正（低风险自动晋升，高风险转人）。
**协议失效时，结果应是「可修复的漂移」，而非「污染正式状态」**——所以脸 ② 永远 fail-closed。

## 实现约束（改 gate.py 时必守）

- 零依赖、CWD 无关（路径参数化）、坏输入优雅退出不崩。
- **不信任自报 `risk_level`**：决策只看 `capabilities`。
- **fail-closed**：危险或未知 capability、缺 manifest、缺 name → 一律不自动晋升。
- 容忍 BOM / 前导空行 / frontmatter 行尾 `#` 注释 / 内联与块式列表。
