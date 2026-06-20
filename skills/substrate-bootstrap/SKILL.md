---
name: substrate-bootstrap
target_runtimes: [claude-code]
risk_level: medium
capabilities: [shell]
reason: 新 agent 自举 + 新机首次接入（git、调用 sync）
---

# substrate-bootstrap — 新 agent 自举

第一次在某 Substrate 实例 / 某台机器上干活时跑这个，把自己配置到可安全维护库的状态。
它把 `governance/bootstrap.md` 的协议变成可执行步骤。

## 何时用

- 一个新 agent 第一次接触某实例。
- 一台新机器第一次接入（含「要 sync 先得有 sync」的种子问题）。
- 用户说「上手 / bootstrap / 接入这台机 / 初始化」。

## 步骤

1. **取仓库**：已 clone 就 `git pull`；没有就 `git clone <实例远程>` 到本机（先配好 git/SSH）。
2. **种子 sync（鸡生蛋）**：把 `substrate-bootstrap` + `substrate-sync` 先放进本 runtime 的 skill 目录（一次性）。此后 sync 能自我维护。
3. **读规则**：读 `governance/CONSTITUTION.md` + `governance/zones.md`（有哪些 zone、谁维护、读写权限）。
4. **配本地身份**：按本机 runtime，确定 git 身份与路径——由对应 `adapter` 决定。本地清单/缓存/身份**不入库**。
5. **装 skill**：调用 `substrate-sync`（即 `python3 <substrate-sync skill 目录>/sync.py --src … --target … --runtime …`），按本机 fleet 角色 + 各 skill 的 `target_runtimes` 选择性安装。
6. **登记本机**：在 `fleet/` 加本机一条（id/role/runtimes）。
7. **就绪自检**：能 pull/push？读过宪法+zones？适用 skill 已装？要写的 zone 的 canonical 与索引位置清楚？
8. **写前**：要动某 zone 前，先读该 zone README 顶部 **Agent Packet**。

## 脚手架一个全新实例（init）

若是「从引擎建新实例」而非接入已有实例：把引擎 `template/` 拷成新目录、替换 `{{INSTANCE_NAME}}`、`git init`、推到用户自己的私有远程，再从第 3 步继续。可选 `substrate-import` 搬入已有内容。

## 版本/迁移

读 `governance/SUBSTRATE_VERSION`。若引擎已发新版（`instance.version < ENGINE_VERSION`），**不要自己迁**——交 `substrate-migrate`，且只在 `fleet/` 标 `migration_leader` 的机器执行。
