# skills — 引擎参考 skill 套件（`substrate-*`）

> 这是**引擎自带**的参考 skill（区别于 `template/skills/`——那是脚手架进用户实例的 skill *分区*）。
> 命名一律 `substrate-*`。**按 phase 真正实现时才建** `skills/substrate-<name>/`，含 `SKILL.md`（+ 顶部 frontmatter = manifest，契约见 `schemas/skill-manifest.schema.yaml`）；
> 多 runtime 变体放同一文件夹的 `SKILL.<runtime>.md`。P0 不提前铺空壳（YAGNI）。

| skill | phase | 作用 |
|---|---|---|
| `substrate-curator` | P1 | 读写/维护知识页 + 执行宪法 |
| `substrate-sync` | P1 | 按角色/registry 选择性安装到各 runtime + 本地清单（回流到 `_incoming` 由 `substrate-intake` 负责） |
| `substrate-doctor` | P1 | 防退化体检 + 毕业阈值监测 + **迁移测试套件**（实现约束见 BUILD-PLAN §15 P1） |
| `substrate-bootstrap` | P1 | 新 agent 自举 |
| `substrate-intake` | P2 | 内容分类器 + 自动回流守门（admission 风险分级） |
| `substrate-import` | P2 | 批量把已有内容搬进新实例 |
| `substrate-migrate` | P3 | 跨引擎版本安全迁移 |
| `substrate-collections` | P5 | 收藏维护 |
| `substrate-memory` | P5 | 共享记忆读写 + 共享/本地边界 |
| `substrate-todo` | P5 | 待办维护 |

> 完整设计见 `docs/BUILD-PLAN.md` §13；开发路线见 §15。
