# 贡献指南（占位）

待开源后补全。要点预留：

- **Engine / Instance 边界是红线**：PR 不得让引擎依赖任何具体用户的内容；不得引入个人数据。
- 新增机制先改 `schemas/` 契约 + `docs/`，再动实现。
- 参考 skill 须带 `skill-manifest`，并通过 admission 风险分级说明。
- 新 runtime 支持以独立 `adapters/<name>/` 提交。
