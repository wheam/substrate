#!/bin/sh
# substrate seed —— 【LEGACY / 旧机制，新用户用不到】
#
# 新用户请用 init-instance.sh：它把 substrate-* 维护 skill **vendor 进实例**，
# clone 实例即自带工具、无鸡生蛋问题（见 README「Quick start」）。
#
# 本脚本只为**早于 vendor 模型的旧实例**保留：它一次性把 substrate-bootstrap + substrate-sync
# 从【引擎仓库】拷进某 runtime 的 skill 目录，解决「要 sync 先得有 sync」的鸡生蛋。
# ⚠️ 它从 $ENGINE/skills 取（引擎仓库），而非实例内 vendored skills——与自包含实例模型相反；
# 自包含实例请直接跑实例内的 skills/substrate-sync/sync.py，不要用本脚本。
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
