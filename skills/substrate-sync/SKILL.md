---
name: substrate-sync
target_runtimes: [claude-code]
risk_level: high
capabilities: [shell, network, install]
reason: 把 skill 装进各 runtime 的 skill 目录（拷文件、按 pin 从网络 clone、写本地清单）
---

# substrate-sync — 选择性安装 skill

把一个 Substrate 实例的 skill 装进**本机 runtime 的 skill 目录**：自写 skill 直接拷，第三方按 `_registry.md` 的 pin 从上游 clone。
按 **fleet 角色 + skill 的 `target_runtimes`** 选择性安装（不 install-all）。本地维护「装了啥」清单，**不入库**。

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

- `--target` 例：Claude Code 是 `~/.claude/skills`（具体由该 runtime 的 **adapter** 给出）。
- 多 runtime 变体：skill 目录里有 `SKILL.<runtime>.md` 就用它落地为该机的 `SKILL.md`；否则用默认 `SKILL.md`。
- 第三方：每条须有 `pin`（无 pin 会标 `CLONE(no-pin!)`，风险）；按 pin clone + checkout。
- 写 `installed-skills.json` 到 `--target`（runtime 的 skill 目录，在实例 repo **之外**，天然 local-only、不入库；仅当 `--target` 被指到实例内某路径时才靠 `.gitignore` 兜底）。

## 鸡生蛋（种子）

「要 sync 先得有 sync」：`substrate-bootstrap` 先把 `substrate-bootstrap` + `substrate-sync` 手动放进 skill 目录种子一次，之后 sync 能自我维护。纯单 runtime 的机器可直接用本脚本自助，不依赖管家。

## 安全

- **默认 dry-run**——先看计划再 `--apply`。
- 安装是副作用（改 runtime 的 skill 目录、可能联网 clone），属高风险操作；在共享机器上 `--apply` 前与用户确认。
