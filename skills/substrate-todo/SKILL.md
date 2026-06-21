---
name: substrate-todo
target_runtimes: [all]
risk_level: medium
capabilities: [shell]
reason: 维护实例根的 TODO.md 待办清单（改文件、跑 git）
---

# substrate-todo — 待办维护

维护一个 **Substrate 实例**的待办清单。设计上**不新开 zone**——待办就是实例根的一个朴素
checklist 文件 **`TODO.md`**（进行中 / 待办 / 已完成 小节）。这是最小、贴合真实实例的做法：
待办是高频、低结构、易过期的东西，给它整套 zone（frontmatter + 互链 + 两级索引 + doctor 入链）
反而是过度设计（YAGNI）。

> 「调用某 skill」= 读它的 `SKILL.md` 并执行；带脚本的 skill 形如 `python3 <该 skill 目录>/xxx.py …`（无独立 CLI 二进制）。本 skill 无脚本——纯文件编辑，按下面流程做即可。

## 何时用

用户说「加个待办 / 记一下要做 X / 标记完成 / 这条做完了 / 看下我的 todo / 清一下 todo / 还有啥没做」。

## TODO.md 的形状（约定，刻意极简）

实例根的 `TODO.md`，**没有 frontmatter、不靠 wikilink 入链**——它是结构页，doctor 对它豁免（见下「与 doctor 的契约」）。固定三小节，GitHub 风格 checklist：

```markdown
# TODO

> 实例根的待办清单，由 `substrate-todo` 维护。完成的条目定期归档/清理，别让本文件无限膨胀。

## 进行中

- [ ] 正在做的事（一行说清）

## 待办

- [ ] 还没开始的事
- [ ] 与知识页相关的，可 [[互链]]（如 跟进 [[some-topic]]）

## 已完成

- [x] 做完的事（YYYY-MM-DD）
```

约定（最小集，需要再长）：
- 每条一行，动词开头，**一行说清**；展不开的细节放对应知识页/项目页，这里只留链接。
- 三小节固定：**进行中 / 待办 / 已完成**。空小节保留标题，写 `- _（空）_` 占位即可。
- 完成时给 `[x]` + 完成日期 `（YYYY-MM-DD）`，便于后续归档。
- 可与 knowledge / projects 页 `[[互链]]`，但**这是单向出链**：被链页不必为 TODO 条目补反向链接（TODO 条目是临时的）。

## 维护流程（每次必守，与其它维护 skill 的 git 流程一致）

1. **同步**：`git pull`（CONSTITUTION 不变量 1）。
2. **读现状**：读实例根 `TODO.md`；不存在则用上面模板新建（模板见 `template/TODO.md`，由 bootstrap 脚手架）。
3. **改**：
   - **加待办** → 追加一条到「待办」（或开工时直接进「进行中」）。先扫一眼三小节**去重**，别重复加同一件事。
   - **开工** → 把条目从「待办」移到「进行中」。
   - **完成** → 把条目改 `[x]` + 完成日期，从「进行中」移到「已完成」。
   - **删除/作废** → 直接删该行（待办本就易过期；要留痕的事项不属于待办，记进知识页）。
4. **保持整洁**（防退化）：
   - 「进行中」别堆太多——同时进行的事项保持少量。
   - 「已完成」定期清理：很旧的完成项删掉或归档（待办不是历史档案；要长期留痕请写进对应知识页/项目页）。
   - 不留空行噪声、不留半句话条目。
5. **自检**：跑 `python3 <substrate-doctor skill 目录>/doctor.py <实例根>`，确认 0 error。TODO.md 被 doctor 豁免（不查孤儿/frontmatter），但别因编辑顺手碰坏别处。
6. **提交**：`git add -A && git commit -m "<说明，如 'todo: 完成 X / 新增 Y'>" && git push`。
7. **汇报**：向用户列出本次对 `TODO.md` 做的增删改（哪几条）。

## 查询流程

1. `git pull`。
2. 读实例根 `TODO.md`，按小节回答（进行中有啥 / 待办还剩啥 / 最近完成了啥）。
3. 条目带 `[[链接]]` 时，可顺着读对应知识/项目页补充上下文。

## 边界

- 本 skill 只管实例根的 `TODO.md`。**它不是知识库**：值得长期留存、跨 agent 有共享价值的东西走 `substrate-curator` 进 `knowledge/`；项目级任务清单可放对应 `projects/<x>/` 页，由 curator 维护。
- 判尺：**临时、会做完、做完就该清** → TODO.md；**持久、要反复查、有共享价值** → 知识页（curator）。
- 不开 zone、不进 `zones.md`、不入两级索引——这是有意为之（见上「设计上不新开 zone」）。

## 与 doctor 的契约（重要）

`TODO.md` 没有 frontmatter、也不靠 wikilink 入链，所以 `substrate-doctor` 必须把**实例根的 `TODO.md` 当结构页豁免**（孤儿 / frontmatter 检查跳过），否则它会被误报成孤儿 + 缺 frontmatter。该豁免在 `doctor.py` 的 `is_structural()` 里实现（本 skill 不改 doctor，见引擎集成项）。
