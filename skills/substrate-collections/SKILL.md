---
name: substrate-collections
target_runtimes: [all]
risk_level: medium
capabilities: [shell]
reason: 维护 collections zone 的行式 canonical（写 data.csv）+ 同步人读分片/计数 + 跑 git
---

# substrate-collections — 收藏维护（行式 canonical）

维护一个 **Substrate 实例**的 `collections/` zone：结构化收藏（工具 / 餐馆 / 书…）。
每个收藏的 **`data.csv` 是单一事实源**；`<name>.md` 索引页与 `by-<dim>/` 分片只是人读视图。

> 「调用某 skill」= 读它的 `SKILL.md` 并执行；带脚本的 skill 形如 `python3 <该 skill 目录>/xxx.py …`（无独立 CLI 二进制）。
> 边界：本 skill 只管 `collections/` 的行式数据；文本知识页归 `substrate-curator`、关于主人的事实归 `substrate-memory`。

## 何时用

用户说「把 X 加进收藏 / 记一个工具(餐馆/书) / 收藏里有没有 Y / 更新某收藏」，或要新建一个收藏类目。

## 核心不变量（doctor 据此判 ERROR，必守）

- **先进主表**：每条先写进 `data.csv`，**每行有稳定 `id`**（slug：全小写、连字符、无空格；同一条永远同 id）。
- **按 id 去重**：写前查 `data.csv` 是否已有该 `id`。已有则**改那一行**，绝不追加重复行。
- **计数一致**：索引页与分片页里的**粗体计数**必须等于 `data.csv` 的数据行数。doctor 只认形如 `**N** 条` / `**N** rows` / `**N** entries` 的粗体数字（普通行文里的数字它不算），三处对不上即 ERROR（「计数漂移」）。改行数后**同步更新所有粗体计数**。

> 计数 = `data.csv` 的**数据行数**（不含表头、不含全空行）。用本 skill 的 `collections.py count` 子命令取权威值，别手数。

## 写入/更新流程（每次必守）

1. **同步**：`git pull`。
2. **定位收藏**：落在 `collections/<name>/`。`<name>` 已存在就用它；要开新类目见下「新建收藏」。
3. **算 id + 去重勘察**：给这条定一个稳定 `id` slug。先看 `data.csv` 是否已有该 id（脚本按 id 去重，但你也要人工判断是不是同一实体换了名）。
4. **写主表（用脚本，默认 dry-run）**：
   ```
   python3 <本 skill 目录>/collections.py upsert \
     --csv <实例根>/collections/<name>/data.csv \
     --field id=<slug> --field name=<显示名> --field <col>=<值> …
   ```
   先不带 `--apply` 看计划（会打印「新增行 / 改某行 / 改后数据行数」）；确认无误再加 `--apply` 真正写。
   - 字段名要对齐 `data.csv` 表头；新字段会作为新列补进表头（缺值的旧行留空）。
   - 值里有逗号/引号/换行交给脚本（用标准库 `csv`，自动加引号转义）。
5. **更新人读视图**：
   - `<name>.md` 索引页：必要时把这条加进常用索引。
   - 命中维度的 `by-<dim>/` 分片页：补一条人读条目。
   - **同步粗体计数**：用 `collections.py count` 取权威行数，把索引页和受影响分片页里的 `**N** 条/rows` 全部改到一致。
6. **同步两级索引**：新增分片文件或新建收藏时，更新 `collections/README.md` 的「收藏清单」表与本收藏 `<name>.md`。
7. **自检**：`python3 <substrate-doctor skill 目录>/doctor.py <实例根>`，修掉所有 ERROR（尤其计数漂移 / 断链 / frontmatter）。
8. **提交**：`git add -A && git commit -m "<说明>" && git push`。
9. **汇报**：列出本次改的所有文件 + 改前/改后行数。

## 查询流程

1. `git pull`。
2. 读 `collections/<name>/<name>.md` 的 Agent Packet 定位；筛选直接读/grep `data.csv`（canonical），分片页只当人读视图。
3. 作答时注明来源（如 "based on collections/tools/data.csv"）。

## 新建收藏（开新类目）

仅当确属一类**结构化、可行式化**的收藏才新开 `collections/<name>/`：

1. 建 `data.csv`，首行表头至少 `id,name`，按内容加列（如 `category,url,description`）。
2. 建 `<name>.md` 索引页：带 frontmatter（`title/created/updated/type`，type 用 `collection`）+ 顶部 **Agent Packet**（zone / 维护 skill / canonical=`data.csv` / 写前查 id / 写后更新分片+计数 / doctor 检查）+ ≥2 个 `[[wikilink]]`。
3. 在 `collections/README.md` 收藏清单表登记一行。
4. 不要过早拆分片：某维度真的多了再开 `by-<dim>/`。

## 毕业阈值意识

`zones.md` 里 collections zone 的 `graduation` 字段声明了升级路径（如 `rows>2000 → 分片 JSONL；需 join → 本地 SQLite 缓存`）。

- doctor 越线只发 **[ADVICE]**，**不自动迁**。看到 advice 时**别在本 skill 里硬迁**。
- 处置：告知用户已越线 + 建议的下一形态；迁移交人确认后由 `substrate-migrate`（迁移 skill）做（有序 / 幂等 / 可验证 / 可回滚，git tag 快照 + doctor 前后校验）。
- 红线：**CSV / JSONL 始终是 canonical；SQLite 永远先做缓存，绝不当事实源。**
