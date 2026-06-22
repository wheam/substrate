# claude-code — Claude Code 适配器

把引擎抽象动作落到 Claude Code：skill 装进 `~/.claude/skills/`，CC 即自动发现并调用（BUILD-PLAN §6.2）。

> 声明在 `adapter.yaml`（顶部可解析 YAML，python3 标准库可读，不假设 PyYAML）。

## 三问回答

- **skill 装到哪**：`~/.claude/skills/`（可用 `CLAUDE_SKILL_DIR` 覆盖，便于测试）。每个 skill = 一个含 `SKILL.md` 的目录。多 runtime skill 取 `SKILL.claude-code.md` 变体（`sync.py` 落地为 `SKILL.md`）。
- **怎么探测 runtime/角色**：PATH 里有 `claude` 可执行体、或 `~/.claude/` 存在 → 视为本 runtime 可用；角色读 `fleet/` 里本机 `role`。
- **本地清单存哪**：`~/.claude/skills/installed-skills.json`，**不入库**（`template/.gitignore` 已忽略）。

## 装 skill（含首次种子）

```sh
# 1) 首次种子（解决「要 sync 先得有 sync」）：先把 bootstrap + sync 放进 skill 目录
mkdir -p ~/.claude/skills
cp -R <instance>/skills/substrate-bootstrap <instance>/skills/substrate-sync ~/.claude/skills/

# 2) 自助跑 sync 装齐其余（默认 dry-run；确认后加 --apply）
python3 ~/.claude/skills/substrate-sync/sync.py \
  --src <instance>/skills --target ~/.claude/skills --runtime claude-code
```

`sync.py` 只装 `target_runtimes` 含 `claude-code`（或 `all`）且符合本机角色的 skill，并把本地清单写进 `--target`。

> 谁来跑：有管家的机器由管家统一装到各 runtime，CC 不用自己动；**纯 CC 机器**直接如上自助。

## 会话启动自检 hook（多机保持一致，推荐）

多机共维时每台副本都可能落后。把下面这段加进 `~/.claude/settings.json`，**每次会话启动**自动跑
`git pull → sync --check → doctor`，让落后的机器不再静默漂移（见 README「多机/多 agent 保持一致」）。
这是模板——把 `<instance>` 换成你的实例绝对路径：

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "cd <instance> && git pull --ff-only -q 2>/dev/null; python3 skills/substrate-sync/sync.py --src skills --runtime claude-code --check || echo '[substrate] skills 落后远程/实例，跑 sync --apply 对齐'; python3 skills/substrate-doctor/doctor.py . | tail -1"
          }
        ]
      }
    ]
  }
}
```

- `--check` 落后会非 0 退出并打印提示（含「本地落后远程」也能发现，见 sync `--check`）。
- `doctor . | tail -1` 给一行体检摘要（`N error, N warn, N advice`）。
- 想更安静可去掉 doctor 那段；想自动对齐可把 `--check ||` 换成 `--apply`（注意会真的写 skill 目录）。
