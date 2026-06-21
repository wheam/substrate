# skills — skill 分发区（execution plane）

> **Agent Packet**
> - zone: skills
> - 维护 skill: `substrate-sync`（安装/更新）、`substrate-intake`（守门 `_incoming/`）
> - canonical: 自写 skill = `skills/<name>/`（真文件）；第三方 = `_registry.md`（只存指针）
> - 写前查: 本 README + `_registry.md`，确认没有重复/同名 skill
> - 写后更新: 本 README 的 skill 清单；新增第三方则加 `_registry.md` 条目
> - doctor 检查: 每个 skill 有合规 manifest（frontmatter）；`_registry` 条目有 pin；`_incoming/` 未滞留未审件

## 三类 skill

1. **自己写的**：`skills/<name>/`，纯文件，跟仓库走。
2. **第三方**：在 `_registry.md` 记指针，**代码不入库**。两种 `kind`：`git`（记 URL+pin，`substrate-sync` 按 pin 从上游 clone）｜`plugin`（插件机制分发的，如 superpowers，记 `source`，sync 不 clone、更新交回插件机制）。
3. **agent 自总结的**：先自动回流到 `_incoming/`，**过 admission 守门（风险分级）才晋升**到 `skills/<name>/`。

> **`substrate-*` 维护 skill**：本实例由 `init-instance.sh` 脚手架时已把引擎的 substrate-curator/doctor/sync/migrate/… **vendor 进本目录**，所以 clone 实例即带维护工具。它们是引擎的副本（单一事实源在引擎）；引擎升级后用 `init-instance.sh --refresh <实例>` 刷新。

## skill 文件夹长什么样

```
skills/<name>/
├── SKILL.md              # 默认/canonical 版：说明 + 顶部 frontmatter = manifest
├── SKILL.<runtime>.md    # 可选：某 runtime 的覆盖版（如 SKILL.claude-code.md）
└── ...                   # 该 skill 需要的其它文件
```

- **manifest = `SKILL.md` 顶部 frontmatter**，字段契约见 Substrate 引擎 `schemas/skill-manifest.schema.yaml`：
  `name / target_runtimes / risk_level`（必填）+ `capabilities / source_agent / reason / dependencies` 等。
- **多 runtime 变体**：同一文件夹放各 runtime 版本，`target_runtimes` 声明适配哪些；runtime 专属的坑（路径、git/SSH、身份）写进对应 `SKILL.<runtime>.md`，**别串台**。

## `_incoming/`（回流隔离区）

- agent 自总结的 skill 落这里，不直接进 `skills/`。
- `substrate-intake` 按 `capabilities` 判风险：只读写 markdown → 可自动晋升；含 shell/network/install/secrets/modify-skills/modify-governance → 转人工 audit（见 `../governance/admission.md`）。
- **不信任 skill 自报的 `risk_level`**，按能力重判。

## 安装（管家模式）

`substrate-sync` 按 **fleet 角色 + skill 的 `target_runtimes`** **选择性安装**（不 install-all）到各 runtime 的 skill 目录，本地维护「装了啥 + 版本」清单（**不入库**）。纯单 runtime 的机器可自助跑 sync，不依赖管家。
