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

## ★ 每次开工前的对齐自检（agent 必做，不必等用户喊）

仓库是多 agent、多机器共维的——你本地的副本/skill 随时可能落后。**每个 session 开始、或刚 `git pull` 之后**，按序自检（廉价、幂等）：

1. **拉新**：`git pull`（基于最新状态再动手）。
2. **对齐 skill**：跑 `substrate-sync --check`——它比对「本机装机时记录的 skills/ 子树」vs「实例当前子树」、列出实例里有本机没装的 skill，并 **best-effort `git fetch` 比对本地 vs 远程上游**。
   - 报 ⚠ 不对齐（退出码 1）→ 若提示「落后远程」先 `git pull`，再跑 `substrate-sync --apply` 把 skill 更新/补齐到当前版本。
   - ★ 这一步即便上面的 `git pull` **静默失败了**（权限/网络）也兜得住：`--check` 自己 fetch 后会发现「本地落后远程」，不会拿没更新的工作树误报「已对齐」。联系不上远程时只提示、不报错。
3. **对齐版本/迁移**：跑 `substrate-migrate`（dry-run，不加 --apply）——若 `instance.version < engine.version` 它会列出 pending 迁移。
   - 有 pending → 交 `substrate-migrate`（多机只在 `migration_leader` 上执行；它备份 tag、出计划、幂等应用、doctor 前后校验）。**别自己乱迁。**
4. **体检**：跑 `substrate-doctor`——确认库健康（断链/孤儿/索引/计数），有 error 先修再写。

> 这套自检让任何 agent（任何 runtime）**自己**就能发现「我的 skill 旧了 / 版本落后了 / 库坏了」并对齐，不依赖用户手动提醒。
> **想做成全自动**：把上面 1–4 接进本 runtime 的 session 启动钩子（如 Claude Code 的 SessionStart hook、Hermes 的启动 hook）。引擎提供检测与例程，钩子由各 runtime 一次性接。
>
> **自愈的前提（部署门槛）**：本 runtime **实际跑命令的身份**（用户/进程）必须能 ① 写 clone 仓库（`git pull`）② 写 skill 目标目录（`sync --apply` 覆盖）③ 读到 git 凭据（私有库认证）。若 agent 以非特权用户运行而仓库/凭据/skill 目录归他人所有，它就够不着、无法自愈——给该身份赋好归属即可。出网无 SSH 时用 **HTTPS + token** 而非 deploy key。

## 版本与迁移

- 本实例基于的引擎版本记在 `governance/SUBSTRATE_VERSION`。
- 若引擎已发新版（`instance.version < engine.version`），**不要自己乱迁**——交给 `substrate-migrate`（它会备份 git tag、出迁移计划给人看、按序幂等应用、doctor 前后校验）。多机时只在标了 `migration_leader` 的机器执行。
