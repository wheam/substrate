#!/bin/sh
# substrate 回归测试 —— 锁住 review 修复过的 bug，杜绝回潮。
# 零依赖：只用 python3 标准库 + git。CWD 无关。每个用例在 mktemp 沙盒里跑，绝不污染引擎仓库。
# 用法: sh tests/run-tests.sh   退出码: 0 全过 / 1 有失败。
set -u

ENGINE="$(cd "$(dirname "$0")/.." && pwd)"
DOC="$ENGINE/skills/substrate-doctor/doctor.py"
GATE="$ENGINE/skills/substrate-intake/gate.py"
COLL="$ENGINE/skills/substrate-collections/collections.py"
SYNC="$ENGINE/skills/substrate-sync/sync.py"
IMP="$ENGINE/skills/substrate-import/import.py"
MIG="$ENGINE/skills/substrate-migrate/migrate.py"

PASS=0; FAIL=0
ok()   { PASS=$((PASS+1)); printf "  ok   - %s\n" "$1"; }
bad()  { FAIL=$((FAIL+1)); printf "  FAIL - %s\n" "$1"; }
# expect_rc <expected-code> <name> <cmd...>
expect_rc() { exp="$1"; name="$2"; shift 2; "$@" >/dev/null 2>&1; rc=$?; [ "$rc" = "$exp" ] && ok "$name" || bad "$name (rc=$rc, expected $exp)"; }

newskill() { d="$1"; shift; mkdir -p "$d"; printf '%b' "$1" > "$d/SKILL.md"; }

echo "== 0) 语法门：编译所有脚本 =="
if find "$ENGINE/skills" "$ENGINE/migrations" -name '*.py' -print0 | xargs -0 python3 -m py_compile 2>/dev/null; then
  ok "py_compile 全部脚本"
else bad "py_compile 全部脚本"; fi

echo "== 1) doctor 在 examples/minimal 与 template 上 0 error =="
expect_rc 0 "doctor examples/minimal（含 committed skill + 多类别分片）" python3 "$DOC" "$ENGINE/examples/minimal"
expect_rc 0 "doctor template" python3 "$DOC" "$ENGINE/template"

echo "== 2) B1: 已提交的自写 skill 不被 doctor 误判 =="
T="$(mktemp -d)/inst"; mkdir -p "$T"; cp -R "$ENGINE/examples/minimal/." "$T/"
mkdir -p "$T/skills/my-helper"
printf -- '---\nname: my-helper\ntarget_runtimes: [claude-code]\nrisk_level: low\ncapabilities: []\n---\n# my-helper\nbody\n' > "$T/skills/my-helper/SKILL.md"
expect_rc 0 "doctor 接受 skills/<name>/SKILL.md（无孤儿/frontmatter 误报）" python3 "$DOC" "$T"

echo "== 3) M: 多类别分片不再触发计数漂移误报 =="
T="$(mktemp -d)/inst"; mkdir -p "$T"; cp -R "$ENGINE/examples/minimal/." "$T/"
# cli 分片诚实写 4（仅 4 条 cli），主表 5 行；新 doctor 不应报错
expect_rc 0 "分片诚实子集计数不误报（主表5/cli分片4）" python3 "$DOC" "$T"

echo "== 4) B2: gate fail-closed（无危险件可绕过晋升）=="
B="$(mktemp -d)"
newskill "$B/safe"    '---\nname: safe\ntarget_runtimes: [claude-code]\nrisk_level: low\ncapabilities: []\n---\nx'
newskill "$B/inline"  '---\nname: inl\ntarget_runtimes: [claude-code]\nrisk_level: low\ncapabilities: [read-markdown, write-markdown]\n---\nx'
newskill "$B/comment" '---\nname: c\ntarget_runtimes: [claude-code]\nrisk_level: low\ncapabilities:\n  - read-markdown\n  # trust me\n  - shell\n---\nx'
newskill "$B/blank"   '---\nname: b\ntarget_runtimes: [claude-code]\nrisk_level: low\ncapabilities:\n  - read-markdown\n\n  - network\n---\nx'
newskill "$B/dup"     '---\nname: d\ntarget_runtimes: [claude-code]\nrisk_level: low\ncapabilities: [read-markdown]\ncapabilities: [shell]\n---\nx'
newskill "$B/emptyblk" '---\nname: e\ntarget_runtimes: [claude-code]\nrisk_level: low\ncapabilities:\n---\nx'
newskill "$B/shell"   '---\nname: s\ntarget_runtimes: [claude-code]\nrisk_level: low\ncapabilities: [shell]\n---\nx'
expect_rc 0 "promote: capabilities []"            python3 "$GATE" "$B/safe"
expect_rc 0 "promote: 安全内联列表"               python3 "$GATE" "$B/inline"
expect_rc 1 "AUDIT: 注释夹在列表项间(含 shell)"   python3 "$GATE" "$B/comment"
expect_rc 1 "AUDIT: 空行夹在列表项间(含 network)" python3 "$GATE" "$B/blank"
expect_rc 1 "AUDIT: capabilities 键重复(后者 shell)" python3 "$GATE" "$B/dup"
expect_rc 1 "AUDIT: 写了键却无项(YAML null)"       python3 "$GATE" "$B/emptyblk"
expect_rc 1 "AUDIT: 内联含 shell"                  python3 "$GATE" "$B/shell"

echo "== 5) collections: 符号链接路径不崩 + 计数与 doctor 同口径 =="
LNDIR="$(mktemp -d)/lnk"; REAL="$(mktemp -d)/real"; mkdir -p "$REAL"; ln -s "$REAL" "$LNDIR"
cp "$COLL" "$LNDIR/collections.py"; printf 'id,name\nfoo,Foo\n' > "$LNDIR/data.csv"
expect_rc 0 "collections.py 经符号链接路径运行不崩" python3 "$LNDIR/collections.py" count --csv "$LNDIR/data.csv"
C="$(mktemp -d)/data.csv"; cp "$ENGINE/examples/minimal/collections/tools/data.csv" "$C"
n1="$(python3 "$COLL" count --csv "$C")"
[ "$n1" = "5" ] && ok "count==5 与 doctor 主表口径一致" || bad "count 口径 (got $n1)"

echo "== 6) sync: registry target_runtimes 真正生效 + own 未声明 fail-closed =="
REG="$(mktemp -d)/_registry.md"
printf '```yaml\nregistry:\n  - name: codex-only\n    upstream_git_url: https://example.com/x.git\n    pin: v1.0.0\n    target_runtimes: [codex]\n```\n' > "$REG"
out="$(CLAUDE_SKILL_DIR=/tmp/none python3 "$SYNC" --src "$ENGINE/skills" --runtime claude-code --registry "$REG" 2>&1)"
echo "$out" | grep -q "0 registry" && ok "registry [codex] 条目对 claude-code 不安装" || bad "registry target_runtimes 未生效"
SK="$(mktemp -d)/skills"; mkdir -p "$SK/nort"; printf -- '---\nname: nort\nrisk_level: low\n---\nno target_runtimes\n' > "$SK/nort/SKILL.md"
out2="$(CLAUDE_SKILL_DIR=/tmp/none python3 "$SYNC" --src "$SK" --runtime claude-code 2>&1)"
echo "$out2" | grep -q "未声明 target_runtimes" && ok "own 缺 target_runtimes → fail-closed 跳过" || bad "own 未声明未 fail-closed"

echo "== 7) import: 漏报的密钥形态被抓 + 非 ASCII 文件名不坍缩 =="
SRC="$(mktemp -d)/src"; mkdir -p "$SRC"; INST="$(mktemp -d)/inst"; mkdir -p "$INST"
printf '# cfg\nexport OPENAI_API_KEY=sk-abc123def456ghi\n' > "$SRC/cfg.md"
printf '# 中文\n内容\n' > "$SRC/笔记一.md"; printf '# 中文二\n内容\n' > "$SRC/笔记二.md"
out="$(python3 "$IMP" --source "$SRC" --instance "$INST" --date 2026-06-21 2>&1)"
echo "$out" | grep -q "REVIEW  cfg.md" && ok "OPENAI_API_KEY= → REVIEW(不导入)" || bad "下划线前缀密钥漏报"
echo "$out" | grep -q "untitled" && bad "非 ASCII 文件名坍缩成 untitled" || ok "非 ASCII 文件名保留 slug 不坍缩"

echo "== 8) doctor: 路径式断链不再被 basename 兜底漏判 =="
T="$(mktemp -d)/inst"; mkdir -p "$T"; cp -R "$ENGINE/examples/minimal/." "$T/"
printf -- '---\ntitle: X\ncreated: 2026-06-21\nupdated: 2026-06-21\ntype: concept\n---\n# X\n坏路径 [[wrong/path/git]] 链接\n' > "$T/knowledge/xref.md"
python3 - "$T/knowledge/README.md" <<'PY'
import sys; p=sys.argv[1]; t=open(p).read(); open(p,'w').write(t.rstrip()+"\n- [[xref]]\n")
PY
out="$(python3 "$DOC" "$T" 2>&1)"; echo "$out" | grep -q "断链.*wrong/path/git" && ok "路径式错链被判断链" || bad "路径式错链漏判"

echo "== 9) migrate: 失败重试不丢操作者提交（B3 数据安全）=="
command -v git >/dev/null 2>&1 || { echo "  (skip: 无 git)"; }
if command -v git >/dev/null 2>&1; then
  FE="$(mktemp -d)/engine"; mkdir -p "$FE/migrations" "$FE/skills/substrate-doctor"
  printf '0.3.0\n' > "$FE/ENGINE_VERSION"; cp "$DOC" "$FE/skills/substrate-doctor/doctor.py"
  cp -R "$ENGINE/migrations/0001-knowledge-tags-field" "$FE/migrations/"
  mkdir -p "$FE/migrations/0002-fails"
  printf 'id: 0002-fails\nfrom_version: "0.2.0"\nto_version: "0.3.0"\ntitle: fail\nrisk_level: low\nidempotent: true\nsteps:\n  - {action: x, verify: y}\n' > "$FE/migrations/0002-fails/migration.yaml"
  printf 'import sys\nif "--check" in sys.argv: sys.exit(1)\nsys.exit(0)\n' > "$FE/migrations/0002-fails/apply.py"
  T="$(mktemp -d)/inst"; mkdir -p "$T"; cp -R "$ENGINE/examples/minimal/." "$T/"
  printf '0.1.0\n' > "$T/governance/SUBSTRATE_VERSION"
  python3 - "$T/knowledge/git.md" <<'PY'
import sys,re; p=sys.argv[1]; t=open(p).read(); open(p,'w').write(re.sub(r'(?m)^tags:.*\n','',t,count=1))
PY
  git -C "$T" init -q; git -C "$T" config user.email t@t; git -C "$T" config user.name t
  git -C "$T" add -A; git -C "$T" commit -qm init
  python3 "$MIG" --instance "$T" --engine "$FE" --apply --yes >/dev/null 2>&1   # 0001 ok, 0002 fail → 停 0.2.0
  printf -- '---\ntitle: Precious\ncreated: 2026-06-21\nupdated: 2026-06-21\ntype: concept\n---\n# Precious\n[[git]]\n' > "$T/knowledge/precious.md"
  python3 - "$T/knowledge/README.md" <<'PY'
import sys; p=sys.argv[1]; t=open(p).read(); open(p,'w').write(t.rstrip()+"\n- [[precious]]\n")
PY
  git -C "$T" add -A; git -C "$T" commit -qm "operator work"
  python3 "$MIG" --instance "$T" --engine "$FE" --apply --yes >/dev/null 2>&1   # 重试，0002 又失败 → 回滚
  [ -f "$T/knowledge/precious.md" ] && ok "重试回滚保留操作者提交（不丢数据）" || bad "重试回滚吞掉操作者提交（数据丢失）"
fi

echo
echo "==== 结果: $PASS passed, $FAIL failed ===="
[ "$FAIL" = 0 ]
