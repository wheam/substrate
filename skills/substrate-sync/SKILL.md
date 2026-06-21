---
name: substrate-sync
target_runtimes: [claude-code]
risk_level: high
capabilities: [shell, network, install]
reason: 把 skill 装进各 runtime 的 skill 目录（拷文件、按 pin 从网络 clone、写本地清单）
---

# substrate-sync — 选择性安装 skill

把一个 Substrate 实例的 skill 装进**本机 runtime 的 skill 目录**：自写 skill 直接拷，第三方按 `_registry.md` 的 pin 从上游 clone。
按 skill 的 `target_runtimes` 选择性安装（不 install-all）；**fail-closed**：未声明 `target_runtimes` 的 skill 一律跳过（要全 runtime 显式写 `[all]`）。本地维护「装了啥」清单，**不入库**。

> 角色（fleet role）维度的选择由**上层 agent / 管家**决定——它按本机角色挑「要同步哪些 skill 目录」喂给本脚本；`sync.py` 本身只机械地按 `target_runtimes` 过滤 runtime。

## 何时用

- `substrate-bootstrap` 第 5 步调用它。
- 用户说「装 skill / 同步 skill / 更新 skill / sync」。
- registry 或自写 skill 有更新，要增量重装。

## 怎么跑

```
# 先看计划（默认 dry-run，不动文件）：
python3 <本 skill 目录>/sync.py --src <实例skills目录或引擎skills> \
        --target <runtime skill 目录> --runtime claude-code \
        --registry <实例>/skills/_registry.md
# 确认无误后真正安装：
… 同样命令 + --apply
```

- `--target` **省略时自动从 `adapters/<runtime>/adapter.yaml` 推断**（如 claude-code → `~/.claude/skills`；generic-filesystem → `$SUBSTRATE_SKILL_DIR` 或 fallback）；也可显式传。`kind: view-layer` 的 adapter（obsidian）会被拒绝，不装 skill。
- 多 runtime 变体：skill 目录里有 `SKILL.<runtime>.md` 就用它落地为该机的 `SKILL.md`；否则用默认 `SKILL.md`。
- 第三方：每条须有 `pin`（无 pin 会标 `SKIP(no-pin!)` 并**拒绝安装**）；按 pin `clone + fetch + checkout FETCH_HEAD`，**任一步失败即视为安装失败**（删除半成品、不写入清单、退出码 1）——绝不静默停在默认分支冒充已 pin。安装成功后**删除 `.git` 冻结为该 commit 快照**（杜绝 stray `git pull` 漂移），并把 commit 记入 `installed-skills.json`。
- 退出码：`0` 全部成功；`1` 有 registry 条目未安装（缺 pin/不可达/检出失败）；`2` 调用错误。
- 写 `installed-skills.json` 到 `--target`（runtime 的 skill 目录，在实例 repo **之外**，天然 local-only、不入库；仅当 `--target` 被指到实例内某路径时才靠 `.gitignore` 兜底）。

## 鸡生蛋（种子）

「要 sync 先得有 sync」：`substrate-bootstrap` 先把 `substrate-bootstrap` + `substrate-sync` 手动放进 skill 目录种子一次，之后 sync 能自我维护。纯单 runtime 的机器可直接用本脚本自助，不依赖管家。

## 安全

- **默认 dry-run**——先看计划再 `--apply`。
- 安装是副作用（改 runtime 的 skill 目录、可能联网 clone），属高风险操作；在共享机器上 `--apply` 前与用户确认。
