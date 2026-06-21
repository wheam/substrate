---
name: substrate-migrate
description: "把个人知识库从旧引擎版本安全迁移到新版本（有序 / 幂等 / 可验证 / 可回滚 / 不丢数据）。当用户说「升级库 / 迁移到新版本」，或一个 agent 发现实例版本落后于引擎版本时使用。"
target_runtimes: [all]
risk_level: high
capabilities: [shell, modify-governance]
reason: 跨引擎版本安全迁移——打 git tag / 改实例内容 / 改 governance 版本 / 可 reset --hard 回滚（见 BUILD-PLAN §9）
---

# substrate-migrate — 跨引擎版本安全迁移

把「引擎版本升级」当数据库迁移做：**有序 / 命名 / 幂等 / 可验证 / 可回滚 / 不丢数据**。
当一个基于引擎旧版的 **Substrate 实例**要升到新版，本 skill 安全地把区间内所有迁移按序应用。
它实现 `docs/BUILD-PLAN.md §9` 的流程，并把 `substrate-doctor` 当**迁移测试套件**（迁移前后跑同一套不变量）。

> high-risk：会打 tag、改实例内容、改 `governance/SUBSTRATE_VERSION`、失败时 `git reset --hard` 回滚。
> **只在 fleet 标 `migration_leader` 的机器上跑**（多机协调，见下）。

## 何时用

- `substrate-bootstrap` 发现 `instance.version < ENGINE_VERSION`，把迁移交给本 skill。
- 用户说「升级引擎 / 迁移到新版 / 有没有 pending 迁移」。
- **绝不在 bootstrap 里顺手迁**——迁移单独、显式、由 leader 机器执行。

## 怎么跑

先 dry-run 看计划（不动任何东西）：

```
python3 <本 skill 目录>/migrate.py --instance <实例根> --engine <引擎根>
```

确认计划后再真正迁移：

```
python3 <本 skill 目录>/migrate.py --instance <实例根> --engine <引擎根> --apply --yes
```

`--engine` 省略时默认 = 本脚本所在引擎仓库根；`--doctor` 省略时按引擎布局自动找 `skills/substrate-doctor/doctor.py`。

读输出 / 退出码：
- **0** = 已最新而跳过 / dry-run 出了计划 / `--apply` 全部迁移成功。
- **1** = 某步 verify 或 doctor 不变量不过 → **已 `git reset --hard` 回滚到 `pre-migrate-<from>` tag** → 转人工。
- **2** = 调用错误（路径不对 / **拒绝在引擎本体上跑** / 实例非 git 仓库 / 有未提交改动 / 迁移文件损坏 / **非交互环境 `--apply` 但缺 `--yes` 确认**）。

## 流程（migrate.py 实现，对应 §9）

1. **检测**：读实例 `governance/SUBSTRATE_VERSION` 与引擎 `ENGINE_VERSION`。`instance >= engine` → **版本闸门跳过**（多机幂等的关键）。
2. **发现 pending**：扫 `migrations/`，取区间 `(instance, engine]` 内的迁移，按 `from_version` 升序排，校验迁移链连续，**且链必须抵达 `ENGINE_VERSION`**（否则即使全部应用实例仍落后于引擎——拒绝并转人工，不报假成功）。
3. **不静默执行**：先生成**迁移计划**并打印（id / from→to / risk / title）。dry-run 到此为止。
4. **前置闸门**（`--apply`）：实例必须是**干净的 git 仓库**（无未提交改动），否则拒绝——保证 tag 快照与回滚可靠；且**迁移前 doctor 必须 0 error**（有既有问题先修，否则无法区分既有问题与迁移引入的问题）。
5. **按序应用**，每个迁移：
   - **备份**：`git tag -f pre-migrate-<from>`（每次都重指向**当前 HEAD = 本次迁移前状态**；零成本回滚点）。⚠️ 不复用旧 tag——版本号命名的 tag 跨多次运行会变陈旧，回滚到陈旧 tag 会吞掉两次运行之间操作者的新提交（数据丢失）。
   - **应用**：跑该迁移的 `apply.py --apply`（幂等变换，输入实例路径）。
   - **该迁移自带 verify**：跑 `apply.py --check`，不过即失败。
   - **整体不变量**：迁移前后各跑 `substrate-doctor`，对比——迁移后必须 **0 error**，且 **md 文件数不减少**（增/拆文件允许、删减不允许——与 schema 认可的「加文件/拆文件」动作一致）、**zone 注册不丢**。
   - 成功 → bump 实例 `SUBSTRATE_VERSION` 到该迁移的 `to_version`。
6. **失败任一步** → `git reset --hard pre-migrate-<from>` + `git clean -fd`（清掉失败 apply 的未跟踪残留，可安全重试）+ 报告 + 转人工。多迁移链中只回滚**当前失败的这一个**；**先前已成功的迁移已各自 commit、实例停在中间版本**（非原始版本）。
7. **成功**：改动留在工作区，**由集成者/人审查后 commit + push**（本 skill 不自动 push）。多迁移连续时会在中间打轻量提交锚定下一个回滚点，集成者可 squash；**中间提交一旦失败（缺 git 身份 / pre-commit hook 拒绝）即回滚本迁移并中止**，绝不带着错位的回滚点继续。

## 安全护栏（关键，改 migrate.py 时必守）

- **拒绝在引擎本体上跑**：若 `--instance` 根存在 `ENGINE_VERSION` 文件 → 这是引擎而非实例 → 退出 2。迁移只能作用于实例。
- 一切破坏性 git（`tag` / `reset --hard`）只在 `--instance` 上执行，**引擎仓库绝不被碰**。
- **不丢数据的多重保证**：git 全历史 + `pre-migrate-<from>` tag 永远可回滚；迁移以追加/变换为主；doctor 前后对比不变量，对不上就回滚；模糊内容由迁移脚本进隔离区，不静默删。

## 多机协调

- 迁移**幂等** + **版本闸门**：leader 机器迁移并 bump 版本后 push；其它机器 pull 看到版本已最新即**跳过**，不重复迁。
- 建议在 `fleet/` 标一台 `migration_leader` 专责执行（`--leader` 仅记录到报告，不改行为）。

## 写一个新迁移（fork 者参考）

每个迁移是 `migrations/<NNNN>-<name>/`，含：
- `migration.yaml`：契约见 `schemas/migration.schema.yaml`（`id / from_version / to_version / title / steps[{action,verify}] / idempotent:true / preserves / rollback / risk_level`）。
- `apply.py`：**幂等变换**，输入实例路径，支持三态——`<root>`（dry-run 列计划）、`--apply`（写盘）、`--check`（verify，本步是否已达成）。零依赖、CWD 无关、坏输入优雅退出。

参考实现：`migrations/0001-knowledge-tags-field/`（给缺 `tags` 字段的知识页补 `tags: []`——一个真实可跑、幂等、纯追加、可回滚的示例）。

> 与 `substrate-doctor` 的关系：doctor 既是日常防退化体检，也是本 skill 的不变量测试套件。迁移后不变量对不上 = doctor 报 error = 触发回滚。
