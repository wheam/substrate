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

# 不让 py_compile / python 往源码目录或只读 HOME 缓存写 pyc（受限环境会 PermissionError）。
export PYTHONPYCACHEPREFIX="$(mktemp -d)"

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
  printf -- '---\ntitle: Precious\ncreated: 2026-06-21\nupdated: 2026-06-21\ntype: concept\n---\n# Precious\n[[git]] 与 [[markdown]]\n' > "$T/knowledge/precious.md"
  python3 - "$T/knowledge/README.md" <<'PY'
import sys; p=sys.argv[1]; t=open(p).read(); open(p,'w').write(t.rstrip()+"\n- [[precious]]\n")
PY
  git -C "$T" add -A; git -C "$T" commit -qm "operator work"
  python3 "$MIG" --instance "$T" --engine "$FE" --apply --yes >/dev/null 2>&1   # 重试，0002 又失败 → 回滚
  [ -f "$T/knowledge/precious.md" ] && ok "重试回滚保留操作者提交（不丢数据）" || bad "重试回滚吞掉操作者提交（数据丢失）"
fi

echo "== 10) B1: sync registry name 路径穿越被拒（不删 target 外目录）=="
if command -v git >/dev/null 2>&1; then
  UP="$(mktemp -d)/up"; mkdir -p "$UP"
  ( cd "$UP" && git init -q && git config user.email a@a && git config user.name a && printf 'name: x\n' > SKILL.md && git add -A && git commit -qm x && git tag v1 ) >/dev/null 2>&1
  WS="$(mktemp -d)"; mkdir -p "$WS/target" "$WS/victim"; printf 'precious\n' > "$WS/victim/marker.txt"
  REG="$WS/reg.md"; printf '```yaml\nregistry:\n  - name: ../victim\n    upstream_git_url: file://%s\n    pin: v1\n    target_runtimes: [claude-code]\n```\n' "$UP" > "$REG"
  python3 "$SYNC" --src "$ENGINE/skills" --target "$WS/target" --runtime claude-code --registry "$REG" --apply >/dev/null 2>&1
  [ -f "$WS/victim/marker.txt" ] && ok "name: ../victim 被拒，target 外目录未被删/写" || bad "路径穿越仍可删 target 外目录"
fi

echo "== 11) B2: import 正文裸 sk-proj 密钥 → REVIEW =="
SRC="$(mktemp -d)/s"; mkdir -p "$SRC"; INST="$(mktemp -d)/i"; mkdir -p "$INST"
printf '# OpenAI\nOpenAI key: sk-proj-AbCd1234EfGh5678IjKl9012MnOp\n' > "$SRC/openai.md"
python3 "$IMP" --source "$SRC" --instance "$INST" --date 2026-06-21 2>&1 | grep -q "REVIEW  openai.md" && ok "裸 sk-proj 密钥判 REVIEW（不入库）" || bad "裸 sk-proj 密钥漏放"

echo "== 12) M3: migrate 链未抵达 ENGINE_VERSION → 拒绝 =="
FE2="$(mktemp -d)/e"; mkdir -p "$FE2/migrations" "$FE2/skills/substrate-doctor"
printf '0.3.0\n' > "$FE2/ENGINE_VERSION"; cp "$DOC" "$FE2/skills/substrate-doctor/doctor.py"
cp -R "$ENGINE/migrations/0001-knowledge-tags-field" "$FE2/migrations/"   # 链只到 0.2.0
T3="$(mktemp -d)/i"; mkdir -p "$T3"; cp -R "$ENGINE/examples/minimal/." "$T3/"; printf '0.1.0\n' > "$T3/governance/SUBSTRATE_VERSION"
expect_rc 1 "链止于0.2.0而引擎0.3.0 → 拒绝(RC1)" python3 "$MIG" --instance "$T3" --engine "$FE2"

echo "== 13) M4: 中间提交失败则回滚中止、不误报成功 =="
if command -v git >/dev/null 2>&1; then
  FE4="$(mktemp -d)/e"; mkdir -p "$FE4/migrations" "$FE4/skills/substrate-doctor"
  printf '0.3.0\n' > "$FE4/ENGINE_VERSION"; cp "$DOC" "$FE4/skills/substrate-doctor/doctor.py"
  cp -R "$ENGINE/migrations/0001-knowledge-tags-field" "$FE4/migrations/"
  mkdir -p "$FE4/migrations/0002-ok"
  printf 'id: 0002-ok\nfrom_version: "0.2.0"\nto_version: "0.3.0"\ntitle: ok\nrisk_level: low\nidempotent: true\nsteps:\n  - {action: x, verify: y}\n' > "$FE4/migrations/0002-ok/migration.yaml"
  printf 'import sys\nsys.exit(0)\n' > "$FE4/migrations/0002-ok/apply.py"
  T4="$(mktemp -d)/i"; mkdir -p "$T4"; cp -R "$ENGINE/examples/minimal/." "$T4/"; printf '0.1.0\n' > "$T4/governance/SUBSTRATE_VERSION"
  python3 - "$T4/knowledge/git.md" <<'PY'
import sys,re; p=sys.argv[1]; t=open(p).read(); open(p,'w').write(re.sub(r'(?m)^tags:.*\n','',t,count=1))
PY
  git -C "$T4" init -q; git -C "$T4" config user.email t@t; git -C "$T4" config user.name t; git -C "$T4" add -A; git -C "$T4" commit -qm init
  printf '#!/bin/sh\nexit 1\n' > "$T4/.git/hooks/pre-commit"; chmod +x "$T4/.git/hooks/pre-commit"   # 让中间提交失败
  out="$(python3 "$MIG" --instance "$T4" --engine "$FE4" --apply --yes 2>&1)"; rc=$?
  v="$(cat "$T4/governance/SUBSTRATE_VERSION")"
  if [ "$rc" = 1 ] && [ "$v" = "0.1.0" ] && ! printf '%s' "$out" | grep -q "✅ 全部"; then ok "中间提交被 hook 拒 → 回滚中止、不误报成功（停 0.1.0）"; else bad "中间提交失败处理不当 (rc=$rc v=$v)"; fi
fi

echo "== 14) M5: doctor 校验 zones 必填字段 =="
T5="$(mktemp -d)/i"; mkdir -p "$T5"; cp -R "$ENGINE/examples/minimal/." "$T5/"
python3 - "$T5/governance/zones.md" <<'PY'
import sys; p=sys.argv[1]; t=open(p).read(); open(p,'w').write(t.replace('    writers: [all]\n','',1))
PY
python3 "$DOC" "$T5" 2>&1 | grep -q "zones 契约" && ok "删 zone 必填字段被 doctor 抓" || bad "doctor 未校验 zones 契约"

echo "== 15) M6: doctor 强制每页 ≥2 互链 =="
T6="$(mktemp -d)/i"; mkdir -p "$T6"; cp -R "$ENGINE/examples/minimal/." "$T6/"
python3 - "$T6/knowledge/git.md" <<'PY'
import sys,re; p=sys.argv[1]; t=open(p).read(); open(p,'w').write(t.replace("[[wikilinks]]","wikilinks"))  # 只剩 1 个 outbound
PY
python3 "$DOC" "$T6" 2>&1 | grep -q "互链不足" && ok "只剩 1 个互链的页被抓" || bad "≥2 互链规则未实现"

echo "== 16) m1: doctor 不误报 ~~~ 围栏内的 wikilink =="
T7="$(mktemp -d)/i"; mkdir -p "$T7"; cp -R "$ENGINE/examples/minimal/." "$T7/"
printf '\n~~~\n[[totally-missing-page]]\n~~~\n' >> "$T7/knowledge/git.md"
python3 "$DOC" "$T7" 2>&1 | grep -q "totally-missing-page" && bad "~~~ 围栏内 wikilink 被误判断链" || ok "~~~ 围栏内 wikilink 不误报"

echo "== 17) 改进B: registry kind=plugin 不被 sync clone，只列出 =="
REGP="$(mktemp -d)/_registry.md"
printf '```yaml\nregistry:\n  - name: superpowers\n    kind: plugin\n    source: m/superpowers\n    target_runtimes: [claude-code]\n```\n' > "$REGP"
outp="$(CLAUDE_SKILL_DIR=/tmp/none python3 "$SYNC" --src "$ENGINE/skills" --runtime claude-code --registry "$REGP" 2>&1)"
{ printf '%s' "$outp" | grep -q "plugin   superpowers" && printf '%s' "$outp" | grep -q "0 registry-git"; } && ok "kind=plugin 只列出、不计入待 clone" || bad "kind=plugin 处理不当"

echo "== 18) 改进B: doctor 对 plugin 条目不要求 pin，但要求 source =="
TP="$(mktemp -d)/i"; mkdir -p "$TP"; cp -R "$ENGINE/examples/minimal/." "$TP/"
printf '```yaml\nregistry:\n  - name: sp\n    kind: plugin\n    source: m/sp\n    target_runtimes: [claude-code]\n```\n' > "$TP/skills/_registry.md"
expect_rc 0 "plugin 有 source → doctor 0 error（不报缺 pin）" python3 "$DOC" "$TP"
printf '```yaml\nregistry:\n  - name: sp\n    kind: plugin\n    target_runtimes: [claude-code]\n```\n' > "$TP/skills/_registry.md"
python3 "$DOC" "$TP" 2>&1 | grep -q "plugin 缺 source" && ok "plugin 缺 source → 报错" || bad "plugin 缺 source 未被抓"

echo "== 19) 改进A: init-instance.sh 脚手架自包含实例（vendor 维护 skill + doctor 0 error）=="
INST="$(mktemp -d)/myi"
sh "$ENGINE/init-instance.sh" "$INST" testname >/dev/null 2>&1
{ [ -f "$INST/skills/substrate-doctor/doctor.py" ] && [ -f "$INST/skills/substrate-sync/sync.py" ]; } && ok "维护 skill 已 vendor 进实例" || bad "维护 skill 未 vendor"
grep -q '^# testname' "$INST/README.md" && ok "{{INSTANCE_NAME}} 已替换" || bad "实例名占位未替换"
find "$INST" -name __pycache__ | grep -q . && bad "vendor 带进了 __pycache__" || ok "未带入 __pycache__"
expect_rc 0 "自包含实例 doctor 0 error" python3 "$DOC" "$INST"
sh "$ENGINE/init-instance.sh" --refresh "$INST" >/dev/null 2>&1 && ok "--refresh 刷新 vendored skill 成功" || bad "--refresh 失败"

echo "== 20) MAJOR: 自包含实例不带 --target 跑 vendored sync → 从同级 adapters 推断目标（不再 exit 2）=="
INST2="$(mktemp -d)/myi2"
sh "$ENGINE/init-instance.sh" "$INST2" t2 >/dev/null 2>&1
[ -f "$INST2/adapters/claude-code/adapter.yaml" ] && ok "adapters 已 vendor 进实例" || bad "adapters 未 vendor 进实例"
# 关键：用【实例内】vendored 的 sync.py、不传 --target，应从实例同级 adapters/ 推断成功（dry-run rc=0）。
OUT2="$(CLAUDE_SKILL_DIR="$(mktemp -d)" python3 "$INST2/skills/substrate-sync/sync.py" --src "$INST2/skills" --runtime claude-code 2>&1)"; rc2=$?
[ "$rc2" = 0 ] && ok "vendored sync 无 --target 推断成功（rc=0，不再 exit 2）" || bad "vendored sync 无 --target 仍失败 (rc=$rc2)"
printf '%s' "$OUT2" | grep -q "从 adapter 推断为" && ok "确实从 vendored adapter 推断出 target" || bad "未从 vendored adapter 推断 target"
printf '%s' "$OUT2" | grep -q "install substrate-doctor" && ok "列出 own skill 安装计划" || bad "未列出 own skill 安装计划"
expect_rc 0 "vendor adapters 后实例 doctor 仍 0 error" python3 "$DOC" "$INST2"

echo "== 21) minor: doctor 剥缩进式代码块 → 缩进代码里示例 [[..]] 不误报，但真断链仍抓 =="
T8="$(mktemp -d)/i"; mkdir -p "$T8"; cp -R "$ENGINE/examples/minimal/." "$T8/"
# 前有空行 + 4 空格缩进的代码示例里放一个不存在的链接 → 不应被判断链
printf '\n示例：\n\n    code with [[indented-example-missing]] here\n' >> "$T8/knowledge/git.md"
python3 "$DOC" "$T8" 2>&1 | grep -q "indented-example-missing" && bad "缩进代码块内 wikilink 被误判断链" || ok "缩进代码块内 wikilink 不误报"
# 防过度剥离：普通正文里的真断链必须仍被抓到（锁住「别把真链接吞掉」）
printf '\n正文真断链 [[prose-really-missing]] 不在代码里。\n' >> "$T8/knowledge/markdown.md"
python3 "$DOC" "$T8" 2>&1 | grep -q "prose-really-missing" && ok "正文真断链仍被抓（未漏报）" || bad "正文真断链被漏报（剥过头）"

echo
echo "==== 结果: $PASS passed, $FAIL failed ===="
[ "$FAIL" = 0 ]
