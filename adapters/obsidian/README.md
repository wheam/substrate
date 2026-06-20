# obsidian — 视图层适配器（非 skill runtime）

Obsidian 是**视图层**，不是 agent runtime（BUILD-PLAN §11）。agent 是「维护层」，人用 Obsidian「浏览/手改」同一个 git 仓库。
本 adapter 只放可选的「锦上添花」配置——删掉它实例照常工作。

> 声明在 `adapter.yaml`（`kind: view-layer`）。它**不声明** `skill_install`/`detect`/`local_manifest`——Obsidian 不装、不执行 skill。

## 为什么零迁移即用

Obsidian 本就读「一堆带 `[[wikilink]]` 的 md 文件夹」，而 Substrate 的 data plane 就是 md + YAML frontmatter + `[[wikilinks]]` + CSV/JSONL。
所以**任意 Substrate 实例今天就能直接用 Obsidian 打开读写**。兼容靠开放格式，不靠专属集成。

## 推荐设置

- **把实例仓库根当 vault 根打开**。
- **减噪**：在 Obsidian「Files & Links → Excluded files」里加入这些非给人读的内务目录：`governance/`、`skills/_incoming/`、`skills/_registry.md`、`raw/`、`.cache/`、`generated/`。它们不该污染 graph 视图与全库搜索。
- **graph 视图**：按 frontmatter `type` 分组着色，弱化 `README.md` 与 `_*` 索引页的视觉权重。

## 每设备布局不入库

`.obsidian/workspace.json` 与 `.obsidian/workspace-mobile.json` 是每台机各自的窗口布局，跨机会冲突，必须 gitignore。
`template/.gitignore` 已含这两条，无需手动加。

## 明确边界

不要把 `obsidian` 写进任何 skill 的 `target_runtimes`，也不要把它当 `fleet/` device 的 `runtime`——它不参与 `substrate-sync` 的选择性安装。
其它 markdown 工具（Logseq、纯编辑器、grep、RAG）同理即插即用；专属格式工具（如 Notion）走 `substrate-import` 的导入适配器互通。
