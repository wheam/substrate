#!/bin/sh
# substrate seed —— 一次性把 substrate-bootstrap + substrate-sync 两个 skill 拷进
# 某个 runtime 的 skill 目录，解决「要 sync 先得有 sync」的鸡生蛋。之后由
# substrate-sync 自我维护（按角色/registry 选择性安装其余 skill）。
#
# 用法:  ./seed.sh [TARGET_SKILL_DIR]      # 默认 ~/.claude/skills
# 幂等:  重跑会覆盖这两个 seed skill，不动其它。
set -eu

ENGINE="$(cd "$(dirname "$0")" && pwd)"
TARGET="${1:-$HOME/.claude/skills}"

echo "substrate seed"
echo "  从: $ENGINE/skills/{substrate-bootstrap, substrate-sync}"
echo "  到: $TARGET"
mkdir -p "$TARGET"
for s in substrate-bootstrap substrate-sync; do
  src="$ENGINE/skills/$s"
  if [ ! -d "$src" ]; then
    echo "  [ERROR] 找不到 $src（请在引擎仓库根运行本脚本）" >&2
    exit 1
  fi
  rm -rf "$TARGET/$s"
  cp -R "$src" "$TARGET/$s"
  echo "  seeded $s"
done

echo "done。下一步：让 agent 跑 substrate-sync 装其余 skill，例如"
echo "  python3 \"$TARGET/substrate-sync/sync.py\" --src \"$ENGINE/skills\" --runtime claude-code   # 先 dry-run"
echo "  ……确认后加 --apply。"
