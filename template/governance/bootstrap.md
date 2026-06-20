# bootstrap — 新 agent 上手协议

> 你是第一次在本仓库干活的 agent？按这几步自举，然后才动手写东西。
> 这套协议本身也烘焙进 `substrate-bootstrap` skill——装了它就自动照做。

## 上手步骤

1. **同步**：`git pull`，确保基于最新状态。（首次在本机：先 clone 实例仓库，配好 git/SSH。）
2. **读规则**：读 `governance/CONSTITUTION.md`（全局不变量）+ `governance/zones.md`（有哪些分区、谁维护、读写权限）。
3. **配本地身份**：按本机所用 runtime，确定 git 身份与本地路径（由对应 `adapter` 决定，见 Substrate 引擎 `adapters/`）。本地清单/缓存/身份 **不入库**。
4. **装 skill**：跑 `substrate-sync`——按本机 fleet 角色 + 各 skill 的 `target_runtimes`，把适用 skill 装进本 runtime 的 skill 目录；本地记一份「装了啥+版本」清单（不入库）。
5. **读 Agent Packet 再动手**：要写某个 zone 前，先读该 zone README 顶部的 **Agent Packet**（维护 skill / canonical 在哪 / 写前查什么 / 写后更新什么 / doctor 检查项）。**稳态读取 = O(相关 zone)，不要通读全库。**
6. **写时守宪法**：先勘察绝不重复建 → 写（frontmatter + 互链 ≥2）→ 同步两级索引 → commit/push → 向所有者汇报本次改了哪些文件。

## 检查自己是否就绪

- [ ] 能 `git pull` / `git push`（身份正确）。
- [ ] 读过 CONSTITUTION + zones。
- [ ] 适用 skill 已装进本 runtime。
- [ ] 知道要写的 zone 的 canonical 在哪、写后要更新哪些索引。

## 版本与迁移

- 本实例基于的引擎版本记在 `governance/SUBSTRATE_VERSION`。
- 若引擎已发新版（`instance.version < engine.version`），**不要自己乱迁**——交给 `substrate-migrate`（它会备份 git tag、出迁移计划给人看、按序幂等应用、doctor 前后校验）。多机时只在标了 `migration_leader` 的机器执行。
