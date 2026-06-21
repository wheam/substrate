---
name: substrate-bootstrap
description: "新 agent / 新机器在一个 Substrate 个人知识库（个人仓库 / 共享状态仓库 / cortex）上首次上手：读宪法/zones、配本地身份、装 skill。当用户问「你有没有我的个人仓库 / 知识库」「这个库是什么 / 你了解我的库吗」「帮我接入 / 上手这个库」，或一个 agent 第一次面对这个仓库、不知道它是什么时使用。"
target_runtimes: [all]
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
2. **装 skill**：实例**自包含**（`skills/` 里已 vendor 了 substrate-* 维护 skill），所以**没有鸡生蛋问题**——直接跑实例里 vendored 的 sync：
   `python3 <实例>/skills/substrate-sync/sync.py --src <实例>/skills --runtime <本机 runtime>`（先 dry-run，再 `--apply`），它会把所有适用 skill（含 sync/bootstrap 自己）按 `target_runtimes` 装进本 runtime 的 skill 目录。
   （旧实例若没 vendor：先用引擎 `seed.sh` 种子 `substrate-bootstrap`+`substrate-sync` 再 sync。）
3. **读规则**：读 `governance/CONSTITUTION.md` + `governance/zones.md`（有哪些 zone、谁维护、读写权限）。
4. **配本地身份**：按本机 runtime，确定 git 身份与路径——由对应 `adapter` 决定。本地清单/缓存/身份**不入库**。
5. **登记本机**：在 `fleet/` 加本机一条（id/role/runtimes）。skill 已在第 2 步按 `target_runtimes` 选择性安装；角色维度由你/管家决定喂哪些 skill。
6. **就绪自检**：能 pull/push？读过宪法+zones？适用 skill 已装？要写的 zone 的 canonical 与索引位置清楚？
7. **写前**：要动某 zone 前，先读该 zone README 顶部 **Agent Packet**。

## 脚手架一个全新实例（init）

若是「从引擎建新实例」而非接入已有实例，用引擎根的 **`init-instance.sh`**（一条命令完成）：

```
<引擎>/init-instance.sh ~/<实例目录> <实例名>
```

它做三件事：① 把 `template/` 拷成新实例；② **把引擎的 substrate-* 维护 skill vendor（拷）进实例 `skills/`**——实例自包含，clone 即带工具（BUILD-PLAN §13）；③ 替换 `{{INSTANCE_NAME}}`。之后 `git init` + 推到你自己的私有远程，再从上面第 2 步（装 skill）继续。可选 `substrate-import` 搬入已有内容。

> **为何 vendor**：让「clone 实例即拿到维护工具」真正成立，且消除鸡生蛋（实例自带 `sync.py`，直接跑即可装齐）。代价：实例里多一份工具副本，**引擎升级后要刷新**（见下「版本/迁移」）。

## 版本/迁移

读 `governance/SUBSTRATE_VERSION`。若引擎已发新版（`instance.version < ENGINE_VERSION`）：**升级仍需引擎仓库在场**（migrations 不 vendor）。

1. `git pull` 引擎。
2. **刷新 vendored 维护 skill**：`<引擎>/init-instance.sh --refresh <实例>`（把实例 `skills/` 里的 substrate-* 更新到引擎新版），再重跑 sync 把更新装进 runtime。
3. **迁数据/布局**：交 `substrate-migrate`（`--engine` 指向引擎仓库），**不要自己迁**，且只在 `fleet/` 标 `migration_leader` 的机器执行。
