---
name: substrate-todo
description: "Maintain to-dos (the todo/ zone: one list for the owner + one per agent). Use when the user says 'add a todo / remind me to do X / my todos / what's left / mark done / clean up todos'. 中文触发：「加个待办 / 记一下要做 X / 我的 todo / 还有啥没做 / 标记完成 / 清一下待办」。"
target_runtimes: [all]
risk_level: medium
capabilities: [shell]
reason: 维护 todo/ zone 的待办清单（主人 + 每个 agent 一份；改文件、跑 git）
---

# substrate-todo — 待办维护（todo/ zone）

维护一个 **Substrate 实例**的待办。**v0.3.0 起待办是一个 zone：`todo/`**——主人一份 `owner.md`，
每个 agent 各一份 `<agent>.md`（按 `fleet/` 派生），统一放 `todo/` 文件夹并带文件级索引。
（v0.2.0 的「实例根单文件 `TODO.md`」已由 migration `0002-todo-zone` 升级到本形态。）

> 「调用某 skill」= 读它的 `SKILL.md` 并执行；带脚本的 skill 形如 `python3 <该 skill 目录>/xxx.py …`。本 skill 无自带脚本——文件编辑 + 复用 `substrate-curator` 的 `curate.py reindex` 刷索引。

## 何时用

「加个待办 / 记一下要做 X / 标记完成 / 这条做完了 / 看下我的（或某 agent 的）todo / 清一下 todo / 还有啥没做」。

## todo/ zone 的形状

```
todo/
├── README.md        # zone 索引（Agent Packet + 文件级索引块，自动维护）
├── owner.md         # 主人的待办
└── <agent>.md       # 每个 agent 一份（如 main-dev.md / railway-fast-assistant.md），按 fleet 角色命名
```

- **每份清单**：带最小 frontmatter（`title / created / updated / type: todo`），正文固定三小节
  **进行中 / 待办 / 已完成**（GitHub 风格 `- [ ]` / `- [x]`）。空小节写 `- _（空）_`。
- **owner.md** = 给主人的；**`<agent>.md`** = 给某个 agent 的活儿。
- 一条一行、动词开头；展不开的细节放对应知识/项目页，这里只留 `[[链接]]`。

## per-agent todo 怎么来（按 fleet 派生）

「有多少个 agent → 有多少份 todo」：清单**对齐 `fleet/`**。

1. 读 `fleet/` 里登记的设备/agent（及其角色）。
2. 对每个该有独立待办的 agent，确保 `todo/<agent>.md` 存在（缺则按模板建，frontmatter `title: 待办 — <agent>`）。
3. fleet 新增 agent → 新建对应 todo 文件；移除 agent → 该 todo 文件归档/删除。
4. **fleet 为空时**：只维护 `owner.md`；不要凭空造 agent 待办（per-agent 由 fleet 驱动，不臆测）。

## 维护流程（每次必守）

1. **同步**：`git pull`。
2. **定位**：主人的事 → `todo/owner.md`；某 agent 的事 → `todo/<agent>.md`（不存在且 fleet 有该 agent 则先建）。
3. **改**：
   - 加待办 → 追加到该清单「待办」（开工就放「进行中」）。先扫一眼**去重**。
   - 开工 → 从「待办」移到「进行中」。
   - 完成 → 改 `[x]` + 完成日期，移到「已完成」。
   - 删除/作废 → 删该行（要留痕的事项不属于待办，记进知识页）。
   - 改页 bump frontmatter 的 `updated`。
4. **刷索引**：新增/删 `todo/*.md` 文件后，跑
   `python3 <substrate-curator 目录>/curate.py reindex --instance <实例根> --dir todo --apply`
   （只改清单内容、没增删文件时不必刷）。
5. **保持整洁**：「进行中」别堆太多；「已完成」定期清理（待办不是历史档案）。
6. **自检**：跑 `python3 <substrate-doctor 目录>/doctor.py <实例根>`，0 error。
7. **提交**：`git add -A && git commit -m "todo: …" && git push`。
8. **汇报**：列出本次对哪份清单的增删改。

## 查询流程

1. `git pull`。2. 读 `todo/README` 看有哪几份清单；读 `owner.md` / 指定 `<agent>.md` 按小节回答。

## 边界

- 本 skill 只管 `todo/` zone。**不是知识库**：值得长期留存、跨 agent 共享价值的东西走 `substrate-curator` 进 `knowledge/`；项目级任务清单放 `projects/<x>/`。
- 判尺：**临时、会做完、做完就清** → todo/；**持久、要反复查** → 知识页（curator）。

## 与 doctor 的契约

`todo/` 是普通内容 zone：每份清单是**带 frontmatter 的内容页**（不再像旧 `TODO.md` 那样靠豁免）。
入链来自 `todo/README` 的索引（reindex 自动登记 → 不报孤儿）；互链 <2 仅 WARN（待办本就少链接，不报错）。
（旧 root `TODO.md` 的结构页豁免仍保留在 doctor 里，用于尚未迁移的实例向后兼容。）
