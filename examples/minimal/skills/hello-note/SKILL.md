---
name: hello-note
target_runtimes: [claude-code]
risk_level: low
capabilities: [read-markdown, write-markdown]
reason: 示例自写 skill——演示一个 committed own-skill（纯读写 markdown）能被 doctor 接受
---

# hello-note — 示例自写 skill

这是 `examples/minimal` 里的一个**已提交的自写 skill**，存在的唯一目的：作为回归夹具，
证明 `substrate-doctor` 不会把 `skills/<name>/SKILL.md` 误判成内容页（孤儿 / 缺
`title/created/updated/type` frontmatter）。它的顶部是 **skill-manifest**（见
`schemas/skill-manifest.schema.yaml`），不是知识页 frontmatter。

doctor 对它的处理：
- 豁免孤儿 / 内容页 frontmatter 检查（它在 `skills/` 下，是执行面而非内容图）。
- 单独做 manifest lint：要有 `name` / `target_runtimes` / `risk_level`（本文件都有 → 无 WARN）。

> fork 者：把自写 skill 放 `skills/<name>/`，第三方 skill 只在 `skills/_registry.md` 记 URL+pin。
