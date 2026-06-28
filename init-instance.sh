#!/bin/sh
# init-instance.sh —— 从引擎脚手架一个【自包含】Substrate 实例。
# 自包含 = 把引擎的 substrate-* 维护 skill **vendor（拷）进实例 skills/**，并把 adapters/ 一并 vendor，
# 这样 clone 实例即同时拿到维护工具（BUILD-PLAN §13 的本意），且 sync 不带 --target 也能从实例内
# 同级 adapters/ 推断安装目录；日常维护不再依赖引擎仓库在场。
# （注意：跨引擎版本【升级/迁移】仍需引擎仓库——migrations/ 不 vendor，见文末。）
#
# 用法:
#   ./init-instance.sh <目标目录> [实例名]       # 脚手架新实例（template + vendored 维护 skill）
#   ./init-instance.sh --refresh <实例目录>      # 仅刷新实例里 vendored 的 substrate-*（引擎升级后用）
#
# 退出码: 0 成功 / 2 调用错误。
set -eu

ENGINE="$(cd "$(dirname "$0")" && pwd)"

# ── 环境预检：快失败、给可操作信息，别让新机器在脚手架半途吐原始 traceback ──
command -v python3 >/dev/null 2>&1 || {
  echo "✗ 需要 python3（脚手架与所有维护 skill 都依赖它，且只用标准库——无需 pip）。请先安装 python3 ≥ 3.8。" >&2; exit 2; }
python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,8) else 1)' 2>/dev/null || {
  echo "✗ 需要 python3 ≥ 3.8（当前 $(python3 -V 2>&1)）。" >&2; exit 2; }
command -v git >/dev/null 2>&1 || \
  echo "⚠ 未检测到 git：脚手架能继续，但下一步『git init / 推到私有 GitHub 远程』需要它——建议先装并登录（gh auth login / SSH key / HTTPS token）。" >&2

vendor_skills() {   # $1 = 实例 skills/ 目录
  dest_skills="$1"
  for d in "$ENGINE"/skills/*/; do
    [ -d "$d" ] || continue
    name="$(basename "$d")"
    rm -rf "$dest_skills/$name"
    cp -R "$d" "$dest_skills/$name"
    rm -rf "$dest_skills/$name/__pycache__"   # 别把字节码缓存带进实例
  done
  # 标记这批 vendored skill 来自哪个引擎版本（execution plane）。
  # doctor 用它 vs governance/SUBSTRATE_VERSION（data plane）比对，抓「--refresh 了 skill 却没 migrate」
  # （或反之）的版本错位。--refresh 重 vendor 时一并更新；migrate 成功后会 bump SUBSTRATE_VERSION，二者复归一致。
  printf '%s\n' "$(cat "$ENGINE/ENGINE_VERSION")" > "$dest_skills/.engine-version"
}

vendor_adapters() {   # $1 = 实例根目录
  # 把引擎 adapters/ 也 vendor 进实例，让自包含实例的 sync 不带 --target 也能从
  # 同级 adapters/ 推断安装目录（修 MAJOR：旧版只 vendor skills/，sync 在实例内找不到 adapter）。
  dest_root="$1"
  rm -rf "$dest_root/adapters"
  cp -R "$ENGINE/adapters" "$dest_root/adapters"
  find "$dest_root/adapters" -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
}

write_engine_source_url() {   # $1 = 实例根；best-effort 由引擎 git origin 推出 raw ENGINE_VERSION URL，写进实例
  # 让无引擎的机器也能 best-effort 看一眼引擎远程版本（substrate-migrate 的提醒用）。非 GitHub 远程则跳过，用户可手填。
  command -v git >/dev/null 2>&1 || return 0
  url="$(git -C "$ENGINE" remote get-url origin 2>/dev/null)" || return 0
  [ -n "$url" ] || return 0
  case "$url" in
    https://github.com/*) slug="${url#https://github.com/}" ;;
    git@github.com:*)     slug="${url#git@github.com:}" ;;
    *) return 0 ;;
  esac
  slug="${slug%.git}"
  branch="$(git -C "$ENGINE" rev-parse --abbrev-ref HEAD 2>/dev/null || echo main)"
  [ -n "$branch" ] && [ "$branch" != "HEAD" ] || branch=main
  printf 'https://raw.githubusercontent.com/%s/%s/ENGINE_VERSION\n' "$slug" "$branch" > "$1/governance/ENGINE_SOURCE_URL"
}

# ── 刷新模式（引擎升级后重新 vendor）──
if [ "${1:-}" = "--refresh" ]; then
  DEST="${2:-}"
  [ -n "$DEST" ] || { echo "用法: init-instance.sh --refresh <实例目录>" >&2; exit 2; }
  [ -d "$DEST/skills" ] || { echo "不是实例目录（无 skills/）: $DEST" >&2; exit 2; }
  vendor_skills "$DEST/skills"
  vendor_adapters "$DEST"
  write_engine_source_url "$DEST"
  echo "已把 vendored 维护 skill + adapters 刷新到引擎当前版本（ENGINE_VERSION=$(cat "$ENGINE/ENGINE_VERSION")）。"
  echo "下一步：重跑 sync 把更新装进 runtime，并跑 doctor 自检。"
  exit 0
fi

# ── 脚手架新实例 ──
DEST="${1:-}"
[ -n "$DEST" ] || { echo "用法: init-instance.sh <目标目录> [实例名]" >&2; exit 2; }
NAME="${2:-$(basename "$DEST")}"
[ -e "$DEST" ] && { echo "目标已存在，拒绝覆盖: $DEST" >&2; exit 2; }

mkdir -p "$DEST"
cp -R "$ENGINE/template/." "$DEST/"
vendor_skills "$DEST/skills"
vendor_adapters "$DEST"
write_engine_source_url "$DEST"

# 填实例名占位（python3 替换，避免 sed 的 BSD/GNU 差异）
python3 - "$DEST/README.md" "$NAME" <<'PY'
import sys
p, name = sys.argv[1], sys.argv[2]
t = open(p, encoding="utf-8").read().replace("{{INSTANCE_NAME}}", name)
open(p, "w", encoding="utf-8").write(t)
PY

n_vendored="$(ls -d "$DEST"/skills/substrate-* 2>/dev/null | wc -l | tr -d ' ')"
echo "✅ 实例已脚手架: $DEST"
echo "   实例名: $NAME   基于引擎版本: $(cat "$ENGINE/ENGINE_VERSION")"
echo "   已 vendor 维护 skill: $n_vendored 个 + adapters/（实例自包含，clone 即带工具 + sync 免 --target）"
echo ""
echo "下一步："
echo "  1) cd \"$DEST\" && git init && git add -A && git commit -m 'init substrate instance'"
echo "  2) 装 skill 到本 runtime（先 dry-run，再 --apply）："
echo "     python3 \"$DEST/skills/substrate-sync/sync.py\" --src \"$DEST/skills\" --runtime claude-code"
echo "  3) 体检： python3 \"$DEST/skills/substrate-doctor/doctor.py\" \"$DEST\""
echo ""
echo "升级引擎到本实例时（仍需引擎仓库）："
echo "  - git pull 引擎 → ./init-instance.sh --refresh \"$DEST\" 刷新 vendored skill"
echo "  - 再跑 substrate-migrate 把数据/布局迁到新版本（--engine 指向引擎仓库）。"
