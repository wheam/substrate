# 术语表（concepts）

> Substrate 全仓库共用的词汇表。schema、参考 skill、治理模板都引用这里的定义；改术语只改这一处，避免漂移。

## 顶层

- **Engine（引擎）**：本仓库（Substrate）。只含机制：模板、schema、参考 skill、adapter、迁移。公开、中立，**不依赖任何用户的偶然事实**。
- **Instance（实例）**：用户私有的个人状态仓库，由 `template/` 脚手架而来，叠在引擎之上。引擎决定「怎么维护」，实例决定「维护什么」。二者是**两个独立 git 仓库**。

## 三层模型

- **Control plane（控制面）**：仓库怎么被维护——`governance/`（宪法、zones、admission、bootstrap、architecture、版本）。回答「什么能写 / 写到哪 / 谁写 / 怎么验证」。
- **Data plane（数据面）**：用户长期个人 context——知识、collections、memory、projects、fleet。
- **Execution plane（执行面）**：能做事的东西 + 本地状态——`skills/`（可版本化）+ 本地清单/缓存/身份（**不入库**）。

> 概念分层，不强制成目录名。

## 控制面

- **Zone（分区）**：仓库里一个有独立 schema + 维护行为 + 访问模式的内容区。每个 zone 在 `governance/zones.md` 顶部的可解析 YAML 块里注册一条，字段契约见 `schemas/zone.schema.yaml`。
- **Governance（治理）**：`governance/` 目录里那套「怎么维护本仓库」的规则与协议。
- **CONSTITUTION（宪法）**：少而硬的全局不变量 + 「新增类型」procedure。所有维护 skill 引用的唯一权威；改规则只改这一处。
- **Admission（准入）**：内容能否进库、以什么形态进的判定规则。核心是**入库四问**与**四种入库去向**（见下）。
- **入库四问**：① 持久？② 属于个人 context？③ 可文件化且适合 git？④ 跨 agent 有共享价值？四问皆是才考虑进库。
- **四种入库去向（admission outcome）**：对**一条新内容**的准入判定结果（页/条目级）。
  - **Canonical**：进库成事实源。
  - **Reference**：只存引用 + 摘要 + 文字代理（不存本体，如多媒体）。
  - **Local-only**：只留本机，不入库。
  - **Forbidden**：密钥 / 凭据 / 敏感原文 / 大二进制——**永不进库**。
  > ⚠️ 别和 zone 级的 `disposition` 字段混淆：那是 `zones.md` 里**整个 zone** 的存储取向，只 `{canonical, reference}` 两值（见 `schemas/zone.schema.yaml`）。此处四种是**单条内容**的准入去向，是不同层级、不同取值集的概念。
- **Zone vs Page**：仅当有独立 schema + 维护行为 + 访问模式才开新顶层 zone；否则是已有 zone 的一页 / 一行。
- **Graduation（毕业）**：一个 zone 随规模增长而升级存储/索引形态的预声明路径（如行式 canonical → 分片 → SQLite 缓存）。写在 zone 的 `graduation` 字段；doctor 监测阈值、越线只提议；执行由迁移 skill / 人确认后 deliberate 做。**SQLite 永远先做缓存，不当 canonical。**

## 索引

- **两级索引**：根 README 只做 **zone 级**路由；每个 zone 的 README 管**本区文件级**索引。取代单点巨表，避免它成为退化源。
- **Agent Packet**：每个 zone README 顶部一段极短的固定字段块——zone / 维护 skill / canonical 在哪 / 写前查什么 / 写后更新什么 / doctor 检查项。让稳态读取 = **O(相关 zone)，永不 O(全库)**，是 context 经济的关键。

## 执行面

- **Skill**：能让 agent 反复做某件事的可执行单元。判 skill 还是知识的尺：想**读**它 = 知识；想让 agent **反复做**它 = skill。
- **三类 skill**：① 自己写的（纯文件，跟仓库走）；② 第三方（`skills/_registry.md` 只存 URL + pin，代码不入库，安装时 clone）；③ agent 自总结的（先自动回流到 `_incoming/`，过 admission 才晋升）。
- **skill-manifest（清单）**：每个 skill 的元信息，存为 `SKILL.md` 顶部 frontmatter，字段契约见 `schemas/skill-manifest.schema.yaml`（含 `target_runtimes` / `risk_level` / `capabilities`）。
- **多 runtime 变体**：一个 skill 文件夹内同放各 runtime 版本——`SKILL.md`（默认/canonical）+ 可选 `SKILL.<runtime>.md` 覆盖（如 `SKILL.claude-code.md`）；manifest 的 `target_runtimes` 声明适配哪些 runtime。
- **`_incoming/`（回流隔离区）**：agent 自总结的 skill 自动落到这里，**过 admission（含风险分级）才晋升**。可执行内容先隔离，是防御纵深的一环。
- **风险分级（risk grading）**：admission 对回流 skill 按 `capabilities` 判风险——只读写 markdown 可自动晋升；凡含 shell / system / network / install / secrets / modify-skills / modify-governance 一律转人工 audit。**不信任 skill 自报的 `risk_level`**。
- **Skill registry**：`skills/_registry.md`——第三方 skill 清单，每条一个可解析 YAML 块（字段见 `schemas/registry.schema.yaml`）。库里只有指针（URL + pin），代码安装时从上游拉。

## 升级 / 防退化

- **Migration（迁移）**：把「引擎版本升级」当数据库迁移做——有序、命名、**幂等**、可验证、**可回滚**（=失败时 `git reset` 到 `pre-migrate-<from>` tag **整体恢复**，**非** vN→vN-1 反向迁移；引擎不提供反向迁移）的 vN→vN+1 变换。有序清单见 `migrations/INDEX.md`，契约见 `schemas/migration.schema.yaml`。任何迁移不丢数据：git tag 快照 + doctor 前后校验 + 模糊内容进隔离区。
- **`SUBSTRATE_VERSION`**：实例在 `governance/SUBSTRATE_VERSION` 记录自己基于的引擎版本（committed）。`instance.version < engine.version` 即有 pending 迁移。
- **Doctor（体检）**：增量防退化体检（断链 / 孤儿 / 索引漂移 / 缺 frontmatter / registry 风险 / 毕业阈值），**同时是迁移的测试套件**（迁移前后跑同一套不变量检查）。为可复现 + 便宜 + 可在 CI 跑，doctor skill 内嵌零依赖的确定性检查（纯 python3 标准库：正则 / glob / csv 解析 frontmatter 与分片，不假设 PyYAML），不依赖独立二进制。

## 机器 / runtime

- **Fleet（舰队）**：用户的多台设备清单 + 每台机角色。引擎只提供通用 `fleet/` 槽位 + 「每台机一次性接入」机制（clone→种子→sync→bootstrap）；**具体有哪几台机、各自角色是实例数据**，不进引擎。
- **Role（角色）**：一台机在 fleet 里的职责标签（如 `main-dev` / `headless-dev` / `migration_leader`）。substrate-sync 按角色 + skill 的 `target_runtimes` 选择性安装。
- **Adapter（适配器）**：把引擎里抽象的动作（装 skill / 读协议 / 写本地清单）落到具体 runtime 的真实路径与机制。声明式，不是代码。是引擎不绑死任何 runtime 的关键。
- **Bootstrap（自举）**：新 agent 上手协议——pull → 读宪法/zones → 配本地身份 → sync 装 skill → 读相关 zone 的 Agent Packet 再动手。
- **contested**：新信息与旧内容冲突时的标记——不静默覆盖，保留两方 + 日期 + 来源，frontmatter 标 `contested: true`，提请所有者复核。
