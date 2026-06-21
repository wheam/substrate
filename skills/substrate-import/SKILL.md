---
name: substrate-import
description: "把已有的一堆 markdown / 笔记 / 文件夹 / Obsidian vault 批量搬进个人知识库。当用户说「把我这些笔记 / 这个文件夹 / 这个 vault 导进库 / 搬进知识库」时使用。"
target_runtimes: [all]
risk_level: medium
capabilities: [shell]
reason: 批量把已有内容搬进新实例（拷文件、补 frontmatter、跑 doctor、交集成提交）
---

# substrate-import — 批量上手迁移器

把用户**现有的一堆东西**（散落 markdown、文件夹、Obsidian vault）批量搬进一个**新 Substrate 实例**，免手动苦力。
区别于 `substrate-migrate`（那是跨引擎版本升级，§9）；本 skill 是「把旧东西搬进一个全新实例」（§10）。

> 「调用某 skill」= 读它的 `SKILL.md` 并执行；带脚本的 skill 形如 `python3 <该 skill 目录>/xxx.py …`（无独立 CLI 二进制）。

## 何时用

- 用户说「把我这个文件夹/vault/笔记导进来 / 批量搬进库 / 初始化时把已有内容拉进来」。
- 新实例 `substrate-bootstrap` 之后的可选第 4 步（init 流程，见 `governance/bootstrap.md`）。

## 核心原则（必守）

- **幂等**：重跑不重复——目标已存在的文件跳过，不二次补 frontmatter。
- **dry-run 默认**：先出**映射计划**给人看，`--apply` 才动文件。
- **审批闸门**：计划→人审→执行。不跳过人审直接批量写。
- **模糊/可疑进隔离，不批量塞垃圾**：文件名/内容疑似含密钥凭据的标 `REVIEW` 不自动搬；来源内撞名的标 `REVIEW` 交人区分。宁缺勿滥。
- **分类是判断，不是脚本能定死的**：`import.py` 只给**保守默认提议**（落 `--zone`，默认 `knowledge/`，保留子目录层级）。
  四去向（Canonical/Reference/Local-only/Forbidden）、该不该换 zone、该不该拆成 skill、剔哪些敏感位——按 `substrate-intake` 的规则逐条判（intake 与本 skill 并行开发；其规则即 `governance/admission.md` 的入库四问 + 四去向 + 风险分级）。

## 流程

1. **同步**：`git pull`（目标实例）。
2. **扫描来源 + 出计划（dry-run）**：
   ```
   python3 <本 skill 目录>/import.py --source <来源目录> --instance <实例根> \
           --adapter generic-md|obsidian [--zone knowledge] [--date YYYY-MM-DD] [--type note]
   ```
   读输出的映射计划：`NEW`（要搬，标是否补 frontmatter）/ `SKIP`（目标已存在，幂等）/ `REVIEW`（敏感/撞名，不自动搬）。
3. **按 intake 规则细分类（判断）**：对每条 `NEW`/`REVIEW`——
   - 套**入库四问**（持久？个人 context？可文件化？跨 agent 共享价值？）筛掉不该进库的。
   - 定**四去向**：Forbidden（密钥/敏感原文/大二进制）**永不进库**；Reference 只存引用+摘要+文字代理；Local-only 不入库；只有 Canonical 才真搬。
   - 定**落哪 zone**：默认 `knowledge/`；明显是项目→`projects/`、明显是收藏行→`collections/`（交对应 skill）、关于主人的稳定事实→`memory/about-owner/`。换 zone 就改 `--zone` 重跑，或分批跑。
   - **想让 agent 反复做的 = skill，不是知识**——别当知识页搬，交 `substrate-intake` 走 `_incoming/` 守门。
   - **剔敏感位**：脚本已挡明显的；细粒度（页内夹带的私钥片段、内部地址）人工剔。
4. **人审批**：把映射计划呈给用户确认（尤其 `REVIEW` 条目与 zone 归属）。
5. **执行（--apply）**：
   ```
   python3 <本 skill 目录>/import.py --source … --instance … --adapter … --date YYYY-MM-DD --apply
   ```
   - 拷文件到目标 zone；给**缺 frontmatter** 的补最小集（`title`/`created`/`updated`/`type`）。
   - `title` 取首个 markdown 标题，没有就用文件名；`created`/`updated` 用 `--date`（不传则留占位符 `YYYY-MM-DD`，事后由 curator 填）。
   - 幂等：已存在的不覆盖。
6. **建初始索引 + Agent Packet**：对**新涉及的 zone 目录**，确保每个目录有 `README.md`，顶部一段 **Agent Packet**（固定字段：zone / 维护 skill / canonical 在哪 / 写前查什么 / 写后更新什么 / doctor 检查项），下方**文件级索引**登记本次搬入的页（文件/摘要/关联）。格式照模板 `template/<zone>/README.md`。这步是判断+写作，由 agent 做（脚本不自动生成索引，避免塞机械垃圾）。
7. **补互链**：搬入的页大多是孤立的——按 `governance/CONSTITUTION.md`，每页 `[[wikilinks]]` ≥ 2 并给被链页补反向链接。量大时分批，先让 doctor 跑通再逐步补链（孤儿是 doctor 的 ERROR）。
8. **跑 doctor**：`python3 <substrate-doctor skill 目录>/doctor.py <实例根>`，修掉 ERROR（断链/孤儿/缺 frontmatter/索引漂移）。
9. **交集成提交**：列出本次搬入/新建/改动的所有文件，交由集成流程 `git add -A && git commit && git push`。

## 来源适配器

| adapter | 来源 | 说明 |
|---|---|---|
| `generic-md` | 一个装 `.md` 的文件夹（可嵌套子目录） | 递归扫 `*.md`，忽略点目录 |
| `obsidian` | Obsidian vault（本质也是 md 文件夹） | 同上，额外忽略 `.obsidian/`、`.trash/`；`[[wikilink]]` 是 Obsidian 原生语法，搬过来零改写 |

> 扩展更多来源（Notion 导出、Apple Notes 导出…）后置；契约是「扫出 (路径, 文本) 列表」，新适配器只需补一个扫描分支。

## 实现约束（改 import.py 时必守）

- 零依赖（python3 标准库）、CWD 无关（路径全参数化）、坏输入优雅退出（路径不对返回码 2，不崩）。
- 副作用默认 dry-run；`--apply` 才写。
- 日期用 `--date` 传入或留占位符，**不取 wall-clock 即时值**（保证可复现、可审计）。
- 幂等：以「目标文件是否已存在」判跳过。
- 敏感检测保守、低误报：命中只标 `REVIEW` 不自动搬，把判断权留给人。
