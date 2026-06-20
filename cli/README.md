# cli — substrate（可选薄壳，skills-first）

> **设计立场：Substrate 是 agent-native 的。** 所有操作的**第一公民是参考 skill**（agent 读 skill 即可执行），
> **不依赖任何编译型 CLI / Node / Python 运行时**。本目录的 `substrate` CLI 是**可选**的薄封装——给人/CI 一个一行入口，
> 内部调用的就是 skill 里同一段逻辑，**不构成第二套真相源**（避免与 skill 漂移）。

## 操作 = skill（权威）

| 操作 | 负责的 skill |
|---|---|
| 脚手架新实例 | `substrate-bootstrap`（+ `template/` 拷贝） |
| 防退化体检 | `substrate-doctor` |
| 按角色选择性装 skill | `substrate-sync` |
| 审查 `_incoming/` 回流件 | `substrate-intake` |
| 新增内容类型 | 走 `governance/CONSTITUTION.md` 的 procedure（`substrate-curator` 协助） |
| 跨引擎版本迁移 | `substrate-migrate` |

## 确定性怎么来（不靠二进制）

`doctor` / `migrate` 需要**可复现**的校验（它是迁移的验收闸门）。这通过在 **skill 内嵌零安装的确定性 shell** 实现——
`grep` 抽 `[[wikilink]]`（**先剥离 inline code 与代码块**，否则讲解语法的反引号会误报断链）做集合差找断链/孤儿、`sort`/`comm` 找索引漂移、
用 **python3 标准库**（**不假设 PyYAML 可用**）做受限子集的 frontmatter 解析比对 schema。
机器上本就有这些工具，agent 逐字跑、解析输出。**skill 是唯一真相源，shell 只是它内嵌的透明实现。**

> 检查豁免集：孤儿 / frontmatter 合规检查**豁免** `governance/*` 与 README/索引/分片这类结构页（它们本就无 frontmatter、靠 path 而非 `[[wikilink]]` 路由）。

## 可选 CLI（后置，非必需）

若将来要给 CI / 不带 agent 的场景一个入口，再做一个**薄** `substrate` 命令包住 skill 里同一段 shell：

```
substrate init <dir>     # 拷 template/ → 新实例
substrate doctor         # 跑 doctor 的确定性检查
substrate sync           # 按本机角色装/更新 skill
substrate admit          # 审 _incoming/
substrate migrate        # 跨版本迁移
```

> 现在**不做**。先把 skill 闭环跑通（见 BUILD-PLAN §15 P1–P3）。
