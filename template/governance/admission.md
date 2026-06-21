# admission — 内容准入规则

> 章程：服务「**持久的、可文件化的、跨 agent 有共享价值的个人 context，以及维护它的规则与工具**」。
> 维护 skill 在写入前用本文件判定：要不要进库、以什么形态、落哪 zone。

## 入库四问（四问皆「是」才考虑进库）

1. **持久？** 是长期有用，还是一次性/临时？
2. **属于个人 context？** 是关于「你 / 你的知识 / 你的事」，还是公共信息随手可查？
3. **可文件化且适合 git？** 能落成文本/结构化文件，diff 友好？
4. **跨 agent 有共享价值？** 别的 agent / 别的设备会需要它？

## 四种去向（disposition）

| 去向 | 含义 | 例 |
|---|---|---|
| **Canonical** | 进库成事实源 | 知识页、收藏主表、共享记忆 |
| **Reference** | 只存引用 + 摘要 + 文字代理，不存本体 | 多媒体、外部长文、PDF |
| **Local-only** | 只留本机，不入库 | 本地清单/缓存/身份、设备私有配置 |
| **Forbidden** | **永不进库** | 密钥、凭据、敏感原文、大二进制 |

> **多媒体 = Reference，库不是云盘**：二进制本体不进库，只放引用 + 元数据 + **文字代理**（转写/OCR/描述/标签）；小图可 git-lfs；agent 操作文字代理，不碰字节。

## zone vs page

仅当有**独立 schema + 独立维护行为 + 独立访问模式**才开新顶层 zone；否则是已有 zone 的一页/一行。开 zone 走 `CONSTITUTION.md` 的「新增类型 procedure」。

## 去重（三层，先查后写）

1. **精确键**：同名/同 slug/同 id？
2. **语义**：内容讲的是不是同一件事？
3. **结构**：是否该并进某已有页的一节，而非新建？

> 相似就**合并不新建**。这是 `CONSTITUTION` 不变量 2 的落地。

## skill 准入（自动回流件的守门）

agent 自总结的 skill 先落 `skills/_incoming/`，由 `substrate-intake` 按 **`capabilities` 判风险**（**不信任 skill 自报的 `risk_level`**）：

- **可自动晋升**：只读写 markdown（risk=low、无危险 capability）。
- **一律转人工 audit**：`capabilities` 含 `shell` / `system` / `network` / `install` / `secrets` / `modify-skills` / `modify-governance` 任一。

> **capability 词表**（`gate.py` 的判定依据）：
> - **安全（可自动晋升）**：`read` / `write` / `read-markdown` / `write-markdown` / `markdown`。
> - **危险（一律 audit）**：`shell` / `system` / `network` / `install` / `secrets` / `modify-skills` / `modify-governance`。
> - **白名单外的未知 capability** 一律按危险处理（fail-closed）。capabilities 键重复、块内夹非列表项行、写了键却无项 → 都转人工，绝不误放。

> 判 skill 还是知识的尺：想**读**它 = 知识（进 knowledge）；想让 agent **反复做**它 = skill（进 skills，过本节守门）。

## 防御纵深

预防（入口横幅 + 写入走 skill）→ 检测（doctor）→ 隔离（危险写入/回流进 `_incoming`/audit）→ 纠正（低风险自动修，高风险转人）。**协议失效时，结果应是「可修复的漂移」，而非「污染正式状态」。**
