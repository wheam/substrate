---
name: substrate-memory
description: "Maintain cross-agent shared memory about the owner (stable facts / preferences / identity). Use when the user says 'remember that I… / my preference is… / about me… / keep this long-term', or whenever any agent needs to know who the owner is and what their personal repo is. 中文触发：「记住我…/ 我的偏好是…/ 关于我…/ 把这个长期记住」。"
target_runtimes: [all]
risk_level: medium
capabilities: [shell]
reason: 读写跨 agent「关于主人」的共享记忆页 + 执行共享/本地边界判定（写内容、跑 git）
---

# substrate-memory — 关于主人的共享记忆

维护一个 **Substrate 实例**的 `memory/about-owner/` 区：**跨 agent 都该知道的、关于主人的稳定事实与偏好**。
记忆就是带 frontmatter 的 markdown 页，按 curator 式流程读写——所以本 skill **不带脚本**（见文末「为何无脚本」）。

> 「调用某 skill」= 读它的 `SKILL.md` 并执行；本 skill 的确定性校验外包给 `substrate-doctor`（`python3 <substrate-doctor skill 目录>/doctor.py <实例根>`）。

## 何时用

- 用户说「记住我喜欢 X / 我的偏好是 Y / 以后都按 Z 来 / 这条关于我，存进共享记忆 / 我之前说过的那个偏好」。
- 任何 agent 学到一条**关于主人本人**、且别的 agent / 别的设备也该知道的稳定事实或偏好时。
- 用户问「关于我你记了什么 / 我的偏好里有没有 X」。

> 边界：**关于主人**的稳定共享事实/偏好 → 本 skill。技术知识/概念/项目 → `substrate-curator`。结构化收藏 → `substrate-collections`。想让 agent 反复做的事 = skill → `substrate-intake`。

## 共享 / 本地边界（写前必判）

这是本 skill 的核心判断：**一条「关于主人」的信息，到底该不该进这个共享区**。按 `governance/admission.md` 的入库四问 + 四去向落判，对 about-owner 具体化为：

| 情形 | 去向 | 怎么处理 |
|---|---|---|
| 稳定、跨 agent 有共享价值的事实/偏好 | **Canonical** | 写进 `memory/about-owner/` |
| 一次性 / 临时 / 仅本机相关（如本次会话的临时上下文、某台机的私有配置） | **Local-only** | **不进库**——留在本地 runtime 的工作记忆里，告诉用户「这条没存共享记忆」 |
| 敏感原文 / 密钥 / 凭据（如完整证件号、密码、私钥） | **Forbidden** | **永不写**。需要时只记「存在某凭据」这一事实，不记原文 |
| 关于外部世界的公共信息（随手可查、与主人无关） | 不属本区 | 走 `substrate-curator` 进 knowledge，或不入库 |

判据速记：**持久？关于主人本人？可文件化且 diff 友好？别的 agent 也需要？** 四问皆「是」才进本区；任一为否，按上表降级。

## privacy: sensitive 与访问收窄

- 本区 `privacy: sensitive`（见 `governance/zones.md`）。写之前再确认内容不含 Forbidden 原文。
- 默认 `readers/writers: [all]`。若某些记忆**只该给特定 runtime** 读/写，由 owner 在 `governance/zones.md` 把 memory 区的 `readers`/`writers` 收窄到具体 runtime（如 `[claude-code]`）——这是治理动作，本 skill 不替 owner 决定，只在察觉边界需求时**提请 owner**。

## 通用槽位命名（不硬编码人名）

`about-owner/` 是**稳定的通用槽位名**。「主人是谁」写在**内容**里（frontmatter 的 `owner: <主人名>`），**绝不进 folder 名、也不进本 skill**。这样引擎与所有实例一致，skill 不绑定任何具体的人。

## 写入 / 更新流程（每次必守）

1. **同步**：`git pull`。
2. **边界判定**：按上面「共享 / 本地边界」定去向。Local-only / Forbidden 直接停手并告知用户，不写库。
3. **勘察去重（先查后写，绝不重复建页）**：读 `memory/about-owner/README.md` 的文件级索引 + 对关键词 `grep`/`glob`。按三层去重判同一事实：
   - **精确键**：同名/同 slug？
   - **语义**：讲的是不是同一件事（同一偏好的不同措辞）？
   - **结构**：该并进某已有页的一节，而非新建？
   命中已有事实 → **更新该页**（bump `updated`，必要时把旧值移入「历史」一行），**不新建**。
4. **冲突 → 标 `contested`，不静默覆盖**：新信息与页里旧事实**矛盾**（而非补充）时，保留两方 + 各自日期 + 来源，frontmatter 标 `contested: true`，并提请 owner 复核。**永不**默默用新值盖旧值。
5. **写页**：
   - 文件名全小写、连字符、无空格（如 `coding-style.md`、`communication-preferences.md`），放 `memory/about-owner/` 下。
   - YAML frontmatter 必备（与本区 README + doctor 对齐）：

     ```yaml
     ---
     title: 记忆标题
     type: memory
     owner: <主人名>
     created: YYYY-MM-DD
     updated: YYYY-MM-DD
     tags: [偏好/事实/...]
     sources: [来源]          # 这条从哪学到的（哪次对话/哪个 agent）
     contested: false         # 仅在出现矛盾时置 true
     ---
     ```

     > doctor 强制 `title/created/updated/type` 四个必填字段；`type` 用 `memory`。
   - 每页 `[[wikilinks]]` **≥ 2**（链到相关记忆页或相关 knowledge 页），并给被链页补反向链接——满足 doctor 的孤儿检测（无入链 = ERROR）。
6. **更新索引（硬规则，二选其一都做）**：在 `memory/about-owner/README.md` 的索引表为本页加一行，**摘要里用 `[[页名]]` wikilink 形式登记**（不要只写裸文件名）。这样**同时**满足 doctor 的「索引漂移」检查与「孤儿」检查（README 的 wikilink 算作该页的一条入链）。
7. **自检**：跑 `python3 <substrate-doctor skill 目录>/doctor.py <实例根>`，把所有 `[ERROR]` 修到 0（断链 / 孤儿 / 缺 frontmatter / 索引漂移）。
8. **提交**：`git add -A && git commit -m "memory: <说明>" && git push`。
9. **汇报**：列出本次创建/更新的文件；若有 Local-only / Forbidden / contested 判定，明确告诉 owner。

## 查询流程

1. `git pull`。
2. 读 `memory/about-owner/README.md` 的索引定位；条目多时 `grep`/`glob` 补充。
3. 读相关页综合作答，注明引用了哪些页（"based on [[coding-style]]"）；遇到 `contested: true` 的页，**把两方都呈现**并提示尚未裁定。

## 为何无脚本（YAGNI）

记忆就是带 frontmatter 的 markdown 页，读写靠上面的 curator 式流程；**没有任何 memory 专属的确定性逻辑需要脚本**：

- frontmatter 合规、孤儿、断链、索引漂移——已由 `substrate-doctor`（`doctor.py`）统一覆盖，本 skill 的第 7 步直接复用它，不重复造检查器。
- 没有行式数据 / 计数 / 风险分级要算（那是 collections / intake 的事）。
- 共享/本地/forbidden 边界与去重/冲突是**判断**，需要 agent 读语义，脚本做不了也不该硬做。

因此本 skill **只交 SKILL.md**。与既有契约的自洽核对：

- **与 doctor 一致**：第 5 步的必填 frontmatter（`title/created/updated/type`）正是 `doctor.py` 的 `REQUIRED_FRONTMATTER`；`memory/about-owner/` 下的页**不在** doctor 的结构页豁免集（非 README、非 `governance/`、非 `_` 前缀、非 `by-*`），故必须靠「≥2 wikilinks + README 用 wikilink 登记」来同时过孤儿与索引漂移两关——第 5、6 步正是为此设计。
- **与 admission 一致**：边界判定四去向（Canonical / Reference / Local-only / Forbidden）= `governance/admission.md`；去重三层（精确键/语义/结构）= admission「去重」节；不静默覆盖 = `CONSTITUTION` 不变量的 `contested` 落地。
- **与 zones / 通用命名一致**：`about-owner/` 通用槽位 + owner 名写进内容 + `privacy: sensitive` + 收窄 readers/writers = `governance/zones.md` 该 zone 注册条目与本区 README。
