---
name: substrate-curator
target_runtimes: [claude-code]
risk_level: medium
capabilities: [shell]
reason: 读写/维护知识页 + 执行宪法（写内容、跑 git）
---

# substrate-curator — 知识维护（可执行的宪法）

维护一个 **Substrate 实例**的内容页（knowledge / projects 等 canonical 文本 zone）。
这是「可执行的宪法」——照本 skill 做，即守 `governance/CONSTITUTION.md`，不必每次重读宪法。

> 「调用某 skill」= 读它的 `SKILL.md` 并执行；带脚本的 skill 形如 `python3 <该 skill 目录>/xxx.py …`（无独立 CLI 二进制）。

## 何时用

用户说「记一下 X / 存进库 / 更新 wiki / 这个值得记录 / 整理到库 / 查一下库里有没有 X」。

## 写入/更新流程（每次必守）

1. **同步**：`git pull`。
2. **判定去向**：按 `governance/admission.md` 入库四问 + 四去向。Forbidden（密钥/敏感原文/大二进制）**永不写**；Reference 只存引用+摘要+文字代理；Local-only 不进库。落哪个 zone 按 `governance/zones.md`。
3. **勘察去重**：读目标 zone README 的文件级索引 + `grep`/`glob` 搜关键词。**绝不重复建页**——相关内容并入已有页（精确键/语义/结构三层去重）。
4. **写页**：
   - 文件名全小写、连字符、无空格。
   - 放对 zone 目录。
   - YAML frontmatter 必备（字段以该 zone schema 为准，至少 `title/created/updated/type`）；改页 bump `updated`。
   - 每页**建议** `[[wikilinks]]` ≥ 2 并给被链页补反向链接（保持知识图连通）——这是**建议**，doctor 只提醒(WARN)不报错。
   - 矛盾不静默覆盖：保留两方+日期+来源，frontmatter 标 `contested: true`，提请用户复核。
5. **同步两级索引**：更新所在 zone README 的文件级索引。可手动写（补摘要/关联更佳），也可跑
   `python3 <本 skill 目录>/curate.py reindex --instance <实例根> --dir <目标目录> --apply`
   自动(重)建该目录 README 的索引块（每页一条）。新增 zone 才动根 README。
6. **自检**：跑 `python3 <substrate-doctor skill 目录>/doctor.py <实例根>`，修掉所有 ERROR。
7. **提交**：`git add -A && git commit -m "<说明>" && git push`。
8. **汇报**：向用户列出本次创建/修改的所有文件。

## 删除一个页（用 curate.py，别手删——会留断链）

删一个内容页时，全库指向它的 `[[wikilink]]` 会变断链。**用 `curate.py rm`**：它删页 + 自动清理全库反向链接（纯导航条目删整行，正文引用去链成纯文本）+ 重建该目录索引。默认 dry-run：

```
python3 <本 skill 目录>/curate.py rm --instance <实例根> --page <相对路径.md>          # 先看计划
python3 <本 skill 目录>/curate.py rm --instance <实例根> --page <相对路径.md> --apply   # 确认后执行
```

删完跑 doctor 复核、再提交。

## 查询流程

1. `git pull`。
2. 读相关 zone README 定位；页多时 `grep`/`glob` 补充。
3. 读相关页，综合作答，注明引用了哪些页（"based on [[page-a]]"）。

## 分类速查（细节见 admission.md / zones.md）

| 内容 | 去哪 |
|---|---|
| 技术原理/方法/概念、实体、对比、个人领悟 | knowledge/（具体子类由实例自定） |
| 个人非代码项目 | projects/ |
| 关于主人的稳定共享事实/偏好 | memory/about-owner/（归 `substrate-memory`，P5） |
| 结构化收藏 | collections/（归 `substrate-collections`，P5） |
| 想让 agent 反复做的事 | 是 skill，不是知识——归 `substrate-intake`，P2 |

> 边界：本 skill 只管 knowledge / projects 等文本内容页。memory 归 `substrate-memory`、收藏行式数据归 `substrate-collections`、skill 回流归 `substrate-intake`。
> **降级**：若这些专用 skill 在当前 phase 尚未安装，不要硬塞——告诉用户该能力在后续 phase 提供，或先按文本页暂存并标注待迁移。
