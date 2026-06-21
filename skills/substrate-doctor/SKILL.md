---
name: substrate-doctor
target_runtimes: [claude-code]
risk_level: medium
capabilities: [shell]
reason: 防退化体检 + 迁移测试套件（只读：运行确定性 shell，不改内容）
---

# substrate-doctor — 防退化体检

对一个 **Substrate 实例**跑确定性体检：断链 / 孤儿 / frontmatter / 索引漂移 / 收藏计数 / registry pin / 毕业阈值。
**只读**——只报告，不自动改。它同时是**迁移的测试套件**（迁移前后各跑一次对比不变量）。

## 何时用

- 用户说「体检 / doctor / 查一下库有没有问题 / 跑一下检查」。
- 任何维护 skill 写完一批后自检。
- `substrate-migrate` 在迁移**前后**各调一次。

## 怎么跑

```
python3 <本 skill 目录>/doctor.py <实例根目录>
```

读输出：
- `[ERROR]` = 必须修（断链/孤儿/缺 frontmatter/索引漂移/计数漂移/registry 缺 pin）。**退出码 1**，CI/迁移闸门据此拒绝。
- `[ADVICE]` = 毕业建议（某收藏越过 `zones.md` 的 `graduation` 阈值）——只提议，由人/迁移 skill 决定。退出码 0。
- 退出码 **2** = 调用错误（如实例路径不对）。CI/迁移闸门用 `exit != 0` 判断，别只判 `== 1`。

修法：按 `governance/CONSTITUTION.md` 把 ERROR 一个个修掉，再重跑到 0 error。

## 检查项（实现见同目录 doctor.py）

| 检查 | 说明 |
|---|---|
| 断链 | `[[wikilink]]` 指向不存在的页（**先剥 inline code/代码块**；路径式链接 `[[a/b]]` 必须按路径命中，不退回 basename 兜底；`skills/` 里的 `[[..]]` 视为示例不计入图） |
| 孤儿 | 内容页无任何入链（**豁免** governance/、`skills/`、README、`_` 前缀、`by-*` 分片） |
| 互链 <2 | 内容页 outbound `[[wikilink]]` 去重后 <2（宪法第 5 条硬规则；同上豁免集，排除自链/code） |
| frontmatter | 内容页缺 `title/created/updated/type`（同上豁免集） |
| 索引漂移 | 同目录有 README.md 时，内容兄弟页须登记在该 README（整词匹配 `.md`） |
| 计数漂移 | **与 `data.csv` 同目录的索引页**声称的「N 条/rows」≠ 主表行数（分类分片 `by-*/` 天然是子集，不参与此校验） |
| zones 契约 | `governance/zones.md` 每个 zone 缺 `path/schema/maintainer_skill/readers/writers` 必填字段、或 id 重复（ERROR）；path 不存在（WARN） |
| registry | `skills/_registry.md` 条目缺 `pin`（ERROR）；pin 是 main/master/HEAD 却未声明 `trusted_floating: true`（WARN） |
| skill 清单（warn） | `skills/<name>/SKILL.md` 应是合规 manifest（缺 `name/target_runtimes/risk_level` → WARN，见 skill-manifest.schema） |
| 毕业（advice） | 收藏行数 > `zones.md` `graduation: rows>N` 阈值 |

## 实现约束（改 doctor.py 时必守）

- **不假设 PyYAML**：frontmatter/zones/registry 用受限子集正则解析（python3 标准库）。
- 抽 `[[wikilink]]` 前**先剥离 inline code 与 fenced code block**。
- 孤儿/frontmatter 检查**豁免** governance/*、`skills/*`（其顶部是 skill-manifest，不是内容页）与 README/索引/分片结构页。
- 计数漂移只校验与 `data.csv` 同目录的索引页；分类分片是子集，不与主表总数比（否则多类别分片必误报）。

> 当作迁移测试套件：迁移前存一份 `doctor` 计数快照，迁移后再跑，不变量对不上就拒绝（回滚到 `pre-migrate-<from>` tag）。
