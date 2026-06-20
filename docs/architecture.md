# 架构原理

> 引擎设计原理的简版。完整的权衡讨论沉淀在引擎仓库之外的私有工作环境中（不随本仓库公开）。

## 核心命题
个人 agent 舰队缺一层**共享状态层**：知识 / 记忆 / 技能 / 清单 / 规则 / 审计，应在一个 git 原生、
可被 agent 操作、可迁移、自描述的系统里。本引擎提供这层的机制与模板。

## 三层模型
- **Control plane（`governance/`）**：仓库怎么被维护——宪法（少而硬的不变量）、分区注册、准入、上手协议。
- **Data plane（知识/收藏/记忆/projects）**：用户长期个人 context。
- **Execution plane（`skills/` + 本地清单）**：能做事的东西（可版本化）+ 本地状态（不入库）。

## 设计原则
1. **读取与库规模解耦**：稳态读取 = O(相关 zone + 命中文件)，永不 O(全库)。规则烘焙进 skill；每个 zone README 顶部放极短「Agent Packet」。
2. **协议是导航，不是强制**：模型不一定守规矩 → 写入走 skill（预防）+ doctor 体检（检测）+ audit（纠正）。失效结果应是「可修复的漂移」，不是「污染正式状态」。
3. **可执行内容先隔离**：skill 自动回流先进 `skills/_incoming/`，过 admission（含风险分级）才晋升。
4. **准入四去向**：canonical / reference / local-only / forbidden（密钥永不进库）。
5. **为毕业而设计**：行式 canonical（CSV→JSONL）→ 本地 SQLite cache → 必要时才 canonical-DB / 拆仓。markdown 可零迁移喂 RAG。
6. **机器可解析的治理**：zones / skill-manifest / registry 都有固定 schema（见 `../schemas/`），doctor 和 sync 不靠猜。
7. **Engine / Instance 分离**：引擎不依赖任何用户偶然事实；instance 不泄露个人内容。
