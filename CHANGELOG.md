# Changelog

本引擎（Substrate）的版本历史。版本号 = 根 `ENGINE_VERSION`；**任何会改实例数据 / schema / 布局的版本都配一个 `migrations/` 迁移**（有序清单见 `migrations/INDEX.md`），由 `substrate-migrate` 有序、幂等、可验证地应用，绝不丢数据（`pre-migrate-<from>` git tag + doctor 前后校验不变量）。

格式参考 [Keep a Changelog](https://keepachangelog.com/)；遵循语义化版本。`ENGINE_VERSION` 始终等于迁移链尾的 `to_version`（由 `tests/run-tests.sh` 的 meta-test 强制）。

## [Unreleased]

> 仅引擎机制 / 检测 / 文档 / 测试增强，**不改实例 schema/数据** → 不 bump `ENGINE_VERSION`、无需迁移。
> （新检测可能让一个原本 0-error 的实例报出此前漏掉的问题，如已提交的密钥——这是检测变严，不是数据迁移。）

- **新 skill `substrate-runtime-context`**：runtime 常驻接入层——生成一张【定量】「上下文小抄」（关于主人记忆 + 各区 Agent Packet + 从 skill description 派生的意图→skill 路由表 + 房规），由 runtime 的 session-start hook 注入，治「意图触发飘 / 记忆不进 agent / 不主动用库」。`render-context.py` 零依赖；超体积上限只 stderr 告警不失败。默认只给对话型助理（Hermes/openclaw）接 hook，claude-code/codex 默认不接（skill 仍 `target_runtimes: [all]`、中立可装，零影响）。
- **刷新机制定为「事件驱动、无定时器、无自动 shell hook」**：常驻小抄在 bootstrap 时由 `wire-context.py --apply` 写一次（路由表/房规/各区地图稳定、长期管用）；之后由 `house-rules` 常驻规则在**写库后**自动刷新、远程更新靠开工自检 `git pull` 在**用库前**带入。**不挂 `on_session_start` 自动 shell hook**——其首次授权 TTY-only（`agent/shell_hooks.py`），网关需 `hooks_auto_accept` 放宽安全，得不偿失。`wire-context.py` 的 `--adapters` 默认 `<instance>/adapters`（自包含实例已 vendor），skill 里免传引擎路径；写后刷新已焙进 `house-rules` + `substrate-curator`。
- **doctor**：新增「about-owner 体积」护栏——`memory/about-owner` 正文总字符超阈值（8000）时 WARN，防常驻小抄膨胀（不改退出码）。
- **runtime 中立的注入通路**：`runtime_context` 提升为**通用 adapter 契约字段**（`adapters/README.md` 文档化：`default_on`/`digest_file`/`inject_via`/`refresh`）。新脚本 `wire-context.py` 通用地读 `adapters/<runtime>/adapter.yaml` 决定开/关并刷新小抄到声明路径——**核心不认任何 runtime 名**，hermes/openclaw/将来任意 agent 走同一通路（给它写个 adapter 块即可，核心零改动）。`generic-filesystem` 补 `runtime_context` 兜底（默认关，显式开启）；`adapters/hermes` 填实为第一个具体 adapter——**注入点已真机验证**：Hermes 原生 context-file 机制（网关 cwd=`~/.hermes` 下 `.hermes.md` 每条消息自动加载，≤20000 字符，安全扫描后注入），故 `digest_file: ~/.hermes/.hermes.md`，**无需改 config、无需重启、逐条消息生效**。
- **文档/onboarding**：`bootstrap.md` + `substrate-bootstrap` + README Option-A 增「让本 runtime 常驻接入」步（agent 读到即可自接）。
- **doctor**：新增「提交密钥/凭据」扫描（Forbidden 红线检测层；高置信形态类 → ERROR，低置信标签启发 → WARN，豁免 `skills/`，`privacy: sensitive` zone 额外标注）。
- **doctor**：新增「引擎版本错位」检测——vendored skill 的引擎版本（`skills/.engine-version`）vs 实例 `SUBSTRATE_VERSION` 不一致时 WARN（抓「--refresh 了 skill 却没 migrate」或反之）。
- **init-instance.sh**：vendor skill 时写 `skills/.engine-version` 标记（供上面的错位检测）。
- **契约**：消歧 `disposition`（页级「入库去向 / admission outcome」vs zone 级存储取向字段，同名不同概念）；澄清 `risk_level` 是人读提示、真正 gating 由 `gate.py` 据 `capabilities` 判定；未消费的 manifest 字段标 `reserved`。
- **测试**：补 upsert 幂等 / doctor 四项正向触发 / 迁移链 meta / 契约 required 一致性 meta / 版本错位 / INDEX 一致性。
- **文档**：MCP 网关提案经对抗式评审改为 **DEFERRED** + 缩 scope + 前置先行 + 替代方案对比（`docs/proposals/mcp-adapter.md`）。

## [0.3.0]

- 迁移 **0002-todo-zone**（0.2.0 → 0.3.0，risk medium）：把根 `TODO.md` 升级成 `todo/` zone（owner + per-agent + 索引）。

## [0.2.0]

- 迁移 **0001-knowledge-tags-field**（0.1.0 → 0.2.0，risk low）：给缺 `tags` 字段的知识页补 `tags: []`。

## [0.1.0]

- 初始版本：Engine/Instance 分离、三层模型（control/data/execution plane）、两级索引 + Agent Packet、准入四问 / 四种入库去向、`substrate-*` skill 套件、`doctor` 防退化体检、迁移机制（有序/幂等/可验证/可回滚）、声明式 adapter。
