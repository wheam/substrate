# migrations — 有序迁移链（INDEX）

引擎跨版本升级的有序迁移清单。

> **运行时不读本文件**：`substrate-migrate` 实际靠扫描 `migrations/*/migration.yaml` + 按 `from_version` 排序执行。本 INDEX 是给**人 / agent** 看的单一可读真相（一眼看全 v→v 历史），并由 `tests/run-tests.sh` 的 meta-test 锁定它与磁盘上的迁移目录**一一对应**（防 INDEX 悄悄漂移）。
>
> **不丢数据保证**：每次迁移先打 `pre-migrate-<from>` git tag（零成本回滚点）+ doctor 前后校验不变量（计数/链接/zone 注册）；失败 `git reset` 回 tag。**回滚 = 整体恢复到 tag，不是 vN→vN-1 反向迁移**（引擎不提供反向迁移）。

| 顺序 | id | from → to | 风险 | 标题 |
|---|---|---|---|---|
| 1 | `0001-knowledge-tags-field` | 0.1.0 → 0.2.0 | low | 给缺 tags 字段的知识页补 `tags: []` |
| 2 | `0002-todo-zone` | 0.2.0 → 0.3.0 | medium | 把根 `TODO.md` 升级成 `todo/` zone（owner + per-agent + 索引）|

当前根 `ENGINE_VERSION` = 链尾 `to_version`（meta-test 强制一致；bump 版本却不加迁移会被 CI 抓）。
