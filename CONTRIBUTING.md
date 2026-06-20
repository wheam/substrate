# 贡献指南

Substrate 是个**中立、可公开**的引擎——只有机制，没有任何具体用户的内容。贡献请守以下几条。

## 红线（PR 必过）

1. **零个人信息**：不得含真实人名、具体机器/网络、密钥、私有路径、某个用户的偏好。示例、测试、提交信息一律中立。
2. **Engine / Instance 可分离**：引擎**不得依赖任何用户的偶然事实**（目录命名约定以外）。用户内容属于另一个私有仓库。
3. **通用命名**：共享记忆槽位是 `memory/about-owner/`（主人名写内容里，不进目录名）；实例名用占位符。

## 怎么改

- **契约先行**：新增/改机制，先改 `schemas/`（zone / skill-manifest / registry / migration）+ `docs/`，再动消费它们的实现。
- **YAGNI**：字段、机制从最小集起步，需要再长。别把库搞复杂。
- **skills-first / 无 CLI**：操作的第一公民是参考 skill；确定性逻辑做成**随 skill 的零依赖 python3 脚本**（标准库，**不假设 PyYAML**），副作用默认 dry-run。
- **参考 skill** 须带 `skill-manifest`（`SKILL.md` 顶部 frontmatter），并能通过 `substrate-intake` 的 capabilities 风险分级。
- **新 runtime 支持** 以独立 `adapters/<name>/`（声明式 `adapter.yaml` + `README.md`）提交。
- **迁移** 当数据库迁移做：有序 / 幂等 / 可验证 / 可回滚 / 不丢数据（见 `docs/BUILD-PLAN.md` §9 + `migrations/0001-*` 参考）。

## 提交前自检

- 跑 `python3 skills/substrate-doctor/doctor.py examples/minimal` —— 必须 **0 error**（CI 也会跑这条）。
- 改了脚本：`find skills migrations -name '*.py' | xargs python3 -m py_compile`。
- 全仓扫一遍无个人信息。

## 提交信息

中立、可公开，说清动了什么、为什么。
