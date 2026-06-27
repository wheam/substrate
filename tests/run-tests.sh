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
SKIP=0
skip() { SKIP=$((SKIP+1)); printf "  skip - %s\n" "$1"; }
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

echo "== 15) M6: doctor 把「每页 ≥2 互链」当【建议】——提醒(WARN)但不报错、不影响退出码 =="
T6="$(mktemp -d)/i"; mkdir -p "$T6"; cp -R "$ENGINE/examples/minimal/." "$T6/"
python3 - "$T6/knowledge/git.md" <<'PY'
import sys,re; p=sys.argv[1]; t=open(p).read(); open(p,'w').write(t.replace("[[wikilinks]]","wikilinks"))  # 只剩 1 个 outbound
PY
OUT6="$(python3 "$DOC" "$T6" 2>&1)"; rc6=$?
printf '%s' "$OUT6" | grep -q "WARN.*互链不足" && ok "互链不足 报为 WARN（提醒）" || bad "互链不足 未报为 WARN"
[ "$rc6" = 0 ] && ok "互链不足 不再让 doctor 失败（退出码 0）" || bad "互链不足 仍导致非 0 退出 (rc=$rc6)"

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
[ "$(cat "$INST/skills/.engine-version" 2>/dev/null)" = "$(cat "$ENGINE/ENGINE_VERSION")" ] && ok "init 写 skills/.engine-version 标记 == ENGINE_VERSION" || bad "init 未写引擎版本标记"
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

CUR="$ENGINE/skills/substrate-curator/curate.py"
echo "== 22) curate reindex: 自动把目录内容页登记进 README 索引（解决索引漂移 + 给入链）=="
T9="$(mktemp -d)/i"; mkdir -p "$T9/knowledge/concepts"
printf -- '---\ntitle: Alpha\ncreated: 2026-01-01\nupdated: 2026-01-01\ntype: concept\n---\n# Alpha\n[[beta]]\n' > "$T9/knowledge/concepts/alpha.md"
printf -- '---\ntitle: Beta\ncreated: 2026-01-01\nupdated: 2026-01-01\ntype: concept\n---\n# Beta\n[[alpha]]\n' > "$T9/knowledge/concepts/beta.md"
expect_rc 0 "reindex dry-run rc=0" python3 "$CUR" reindex --instance "$T9" --dir knowledge/concepts
[ -f "$T9/knowledge/concepts/README.md" ] && bad "dry-run 不该写 README" || ok "reindex dry-run 不写盘"
python3 "$CUR" reindex --instance "$T9" --dir knowledge/concepts --apply >/dev/null 2>&1
{ grep -q '\[\[alpha\]\]' "$T9/knowledge/concepts/README.md" && grep -q '\[\[beta\]\]' "$T9/knowledge/concepts/README.md"; } && ok "两个页都登记进 README 索引" || bad "页未登记进索引"
# 幂等：再跑一次不应重复堆叠（仍只各一条）
python3 "$CUR" reindex --instance "$T9" --dir knowledge/concepts --apply >/dev/null 2>&1
[ "$(grep -c '\[\[alpha\]\]' "$T9/knowledge/concepts/README.md")" = 1 ] && ok "reindex 幂等（不重复堆叠）" || bad "reindex 重复堆叠了"

echo "== 23) curate rm: 删页 + 自动清全库反向链接（删后 doctor 无新断链）=="
T10="$(mktemp -d)/i"; mkdir -p "$T10/knowledge/concepts"
printf -- '---\ntitle: Keep\ncreated: 2026-01-01\nupdated: 2026-01-01\ntype: concept\n---\n# Keep\n见 [[doomed]] 这一篇。\n\n- [[doomed]]\n- [[other]]\n' > "$T10/knowledge/concepts/keep.md"
printf -- '---\ntitle: Other\ncreated: 2026-01-01\nupdated: 2026-01-01\ntype: concept\n---\n# Other\n[[keep]]\n' > "$T10/knowledge/concepts/other.md"
printf -- '---\ntitle: Doomed\ncreated: 2026-01-01\nupdated: 2026-01-01\ntype: concept\n---\n# Doomed\n[[keep]] [[other]]\n' > "$T10/knowledge/concepts/doomed.md"
expect_rc 0 "rm dry-run rc=0" python3 "$CUR" rm --instance "$T10" --page knowledge/concepts/doomed.md
[ -f "$T10/knowledge/concepts/doomed.md" ] && ok "rm dry-run 不真删" || bad "dry-run 误删了文件"
python3 "$CUR" rm --instance "$T10" --page knowledge/concepts/doomed.md --apply >/dev/null 2>&1
[ -f "$T10/knowledge/concepts/doomed.md" ] && bad "rm --apply 未删文件" || ok "页已删除"
grep -q '\[\[doomed\]\]' "$T10/knowledge/concepts/keep.md" && bad "反向链接 [[doomed]] 未清理（残留断链）" || ok "全库反向链接已清（无残留 [[doomed]]）"
grep -q '\[\[other\]\]' "$T10/knowledge/concepts/keep.md" && ok "只清指向被删页的链接，别的链接（[[other]]）保留" || bad "误删了无关链接"
python3 "$DOC" "$T10" 2>&1 | grep -q "断链" && bad "删页后仍有断链" || ok "删页后 doctor 无断链"

echo "== 24) substrate-* 维护 skill 是 runtime 中立（target [all]）→ 也装进非 claude-code runtime（如 hermes）=="
# 多 runtime 共享层的前提：每个 runtime 都能拿到维护 skill。锁住「不再只 for claude-code」。
grep -L "^target_runtimes: \[all\]" "$ENGINE"/skills/substrate-*/SKILL.md | grep -q . \
  && bad "有 substrate-* 未声明 target [all]" || ok "全部 substrate-* 都是 target [all]"
OUT24="$(CLAUDE_SKILL_DIR=x HERMES_SKILL_DIR="$(mktemp -d)" python3 "$SYNC" --src "$ENGINE/skills" --runtime hermes 2>&1)"
printf '%s' "$OUT24" | grep -q "install substrate-doctor" && ok "substrate-doctor 计划装进 hermes runtime" || bad "substrate-* 未装进 hermes"

echo "== 25) migration 0002-todo-zone: root TODO.md → todo/ zone（内容无损 + 幂等 + 迁后 doctor 0 error）=="
APP2="$ENGINE/migrations/0002-todo-zone/apply.py"
T11="$(mktemp -d)/inst"; mkdir -p "$T11"; cp -R "$ENGINE/template/." "$T11/"
rm -rf "$T11/todo"   # 退化成 v0.2.0 形态：无 todo zone、有 root TODO.md
python3 - "$T11/governance/zones.md" <<'PY'
import sys,re; p=sys.argv[1]; t=open(p,encoding="utf-8").read()
open(p,"w",encoding="utf-8").write(re.sub(r"  - id: todo\n(?:    .*\n)*\n?","",t))
PY
printf '# TODO\n\n## 进行中\n- [ ] 锚点待办XYZ\n## 待办\n- _（空）_\n## 已完成\n- _（空）_\n' > "$T11/TODO.md"
expect_rc 0 "0002 dry-run rc=0" python3 "$APP2" "$T11"
[ -d "$T11/todo" ] && bad "dry-run 不该建 todo/" || ok "0002 dry-run 不写盘"
python3 "$APP2" "$T11" --apply >/dev/null 2>&1
{ [ -f "$T11/todo/owner.md" ] && [ -f "$T11/todo/README.md" ]; } && ok "建了 todo/owner.md + README" || bad "todo/ 未建全"
grep -q "锚点待办XYZ" "$T11/todo/owner.md" && ok "root TODO 内容无损搬入 owner.md" || bad "待办内容丢失"
[ -f "$T11/TODO.md" ] && bad "root TODO.md 未删" || ok "root TODO.md 已删"
grep -qE "^\s*- id:\s*todo\b" "$T11/governance/zones.md" && ok "todo zone 已注册进 zones.md" || bad "todo zone 未注册"
expect_rc 0 "0002 --check 达标" python3 "$APP2" "$T11" --check
python3 "$APP2" "$T11" --apply 2>&1 | grep -q "幂等\|无需改动" && ok "0002 幂等（再跑无改动）" || bad "0002 非幂等"
expect_rc 0 "迁移后 doctor 0 error" python3 "$DOC" "$T11"

echo "== 26) sync --check: 检测 skill 是否与实例版本对齐（agent 自检对齐用）=="
T12="$(mktemp -d)/inst"
sh "$ENGINE/init-instance.sh" "$T12" t12 >/dev/null 2>&1
( cd "$T12" && git init -q && git -c user.name=t -c user.email=t@t add -A && git -c user.name=t -c user.email=t@t commit -q -m init )
SKD="$(mktemp -d)"
CLAUDE_SKILL_DIR="$SKD" python3 "$T12/skills/substrate-sync/sync.py" --src "$T12/skills" --runtime claude-code --apply >/dev/null 2>&1
grep -q '"skills_tree": "[0-9a-f]' "$SKD/installed-skills.json" && ok "apply 把 skills/ 子树哈希记进清单" || bad "清单未记录 skills_tree"
expect_rc 0 "刚装完 --check 报对齐(rc=0)" env CLAUDE_SKILL_DIR="$SKD" python3 "$T12/skills/substrate-sync/sync.py" --src "$T12/skills" --runtime claude-code --check
# 非 skill 提交（改知识页）→ 不应误报漂移（skills/ 子树没变）
( cd "$T12" && printf -- '---\ntitle: N\ncreated: 2026-01-01\nupdated: 2026-01-01\ntype: note\n---\n[[a]] [[b]]\n' > knowledge/n.md && git -c user.name=t -c user.email=t@t add -A && git -c user.name=t -c user.email=t@t commit -q -m content )
expect_rc 0 "非 skill 提交后 --check 仍对齐(不误报)" env CLAUDE_SKILL_DIR="$SKD" python3 "$T12/skills/substrate-sync/sync.py" --src "$T12/skills" --runtime claude-code --check
# 改 skill → 应报漂移
( cd "$T12" && printf '\n# tweak\n' >> skills/substrate-todo/SKILL.md && git -c user.name=t -c user.email=t@t add -A && git -c user.name=t -c user.email=t@t commit -q -m skillchange )
expect_rc 1 "skill 变更后 --check 报漂移(rc=1)" env CLAUDE_SKILL_DIR="$SKD" python3 "$T12/skills/substrate-sync/sync.py" --src "$T12/skills" --runtime claude-code --check

echo "== 27) sync --check: 本地落后远程 → 不误报对齐（堵假对齐：pull 静默失败也能发现自己落后）=="
ORIGIN3="$(mktemp -d)/origin.git"; git init -q --bare "$ORIGIN3"
T13="$(mktemp -d)/inst"
sh "$ENGINE/init-instance.sh" "$T13" t13 >/dev/null 2>&1
( cd "$T13" && git init -q && git -c user.name=t -c user.email=t@t add -A && git -c user.name=t -c user.email=t@t commit -q -m init \
  && git branch -M main && git remote add origin "$ORIGIN3" && git -c protocol.file.allow=always push -q -u origin main ) 2>/dev/null
SKD3="$(mktemp -d)"
CLAUDE_SKILL_DIR="$SKD3" python3 "$T13/skills/substrate-sync/sync.py" --src "$T13/skills" --runtime claude-code --apply >/dev/null 2>&1
expect_rc 0 "落后前 --check 报对齐(rc=0)" env CLAUDE_SKILL_DIR="$SKD3" python3 "$T13/skills/substrate-sync/sync.py" --src "$T13/skills" --runtime claude-code --check
# 另一个 clone 改 skill 推到 origin → T13 落后远程，但自己没 pull（工作树/HEAD 没变）
CL2="$(mktemp -d)/c2"; git -c protocol.file.allow=always clone -q "$ORIGIN3" "$CL2" 2>/dev/null
( cd "$CL2" && printf '\n# remote tweak\n' >> skills/substrate-todo/SKILL.md && git -c user.name=t -c user.email=t@t add -A && git -c user.name=t -c user.email=t@t commit -q -m remotechange && git -c protocol.file.allow=always push -q origin main ) 2>/dev/null
# 前置自检：本环境能否用【本地裸库】建立「落后远程」状态？GitHub runner 默认禁 git 'file' 传输
# （CVE-2022-39253，且非 config 能覆盖）→ 上面的 push/clone 建立不起来。用与 sync.py 同口径的【普通 fetch】
# 探测：fetch 后 HEAD 是否真落后 @{u}≥1。建立不起来就【跳过】本断言（非失败），它只在放行 file 传输的环境验证。
git -C "$T13" fetch -q 2>/dev/null
if [ "$(git -C "$T13" rev-list --count 'HEAD..@{u}' 2>/dev/null || echo 0)" -ge 1 ] 2>/dev/null; then
  expect_rc 1 "本地落后远程 → --check 报不对齐(rc=1)" env CLAUDE_SKILL_DIR="$SKD3" python3 "$T13/skills/substrate-sync/sync.py" --src "$T13/skills" --runtime claude-code --check
else
  skip "本地落后远程检测（本环境禁 git 'file' 传输，建立不起落后状态——CI 常见；本断言在放行 file 传输处验证）"
fi

echo "== 28) migrate: 无引擎干净跳过(Fix1) + 显式--engine指错仍报错 + 远程版本提醒(Fix3) =="
T14="$(mktemp -d)/inst"
sh "$ENGINE/init-instance.sh" "$T14" t14 >/dev/null 2>&1
VMIG="$T14/skills/substrate-migrate/migrate.py"
rm -f "$T14/governance/ENGINE_SOURCE_URL"   # 测试隔离：不打真网络
# Fix1: 自包含实例(无引擎)+ 未传 --engine → 干净跳过 rc0（原来 rc2）
expect_rc 0 "无引擎+未传--engine → 干净跳过(rc0)" python3 "$VMIG" --instance "$T14"
# Fix1: 显式 --engine 指到无 ENGINE_VERSION 的目录 → 仍报错 rc2（区分"指错"与"本机无引擎"）
EMPTY14="$(mktemp -d)"
expect_rc 2 "显式--engine指错(无ENGINE_VERSION) → 报错(rc2)" python3 "$VMIG" --instance "$T14" --engine "$EMPTY14"
# Fix3: 配 ENGINE_SOURCE_URL 指向更新版本 → 输出含远程版本号(提醒升级)
printf '9.9.9\n' > "$(dirname "$T14")/remote_ver"
printf 'file://%s/remote_ver\n' "$(dirname "$T14")" > "$T14/governance/ENGINE_SOURCE_URL"
python3 "$VMIG" --instance "$T14" 2>&1 | grep -q "9.9.9" && ok "Fix3: 远程有新版 → 提醒(含版本号)" || bad "Fix3: 未提醒远程新版"
# Fix3: URL 不可达 → 非致命(仍 rc0)
printf 'file:///nonexistent/xyz\n' > "$T14/governance/ENGINE_SOURCE_URL"
expect_rc 0 "Fix3: URL不可达 → 非致命(rc0)" python3 "$VMIG" --instance "$T14"

echo "== 29) 红线: 提交进内容 zone 的密钥被 doctor 判 ERROR（密钥永不进库）=="
T29="$(mktemp -d)/i"; mkdir -p "$T29"; cp -R "$ENGINE/examples/minimal/." "$T29/"
# 往既有内容页追加一个 GitHub token 形态的串（不引入孤儿/索引/frontmatter 错，只测密钥那一项）
printf '\n泄漏: ghp_0123456789abcdefghij0123\n' >> "$T29/knowledge/git.md"
OUT29="$(python3 "$DOC" "$T29" 2>&1)"; rc29=$?
printf '%s' "$OUT29" | grep -q "疑似密钥" && ok "内容页里的密钥被判 ERROR" || bad "内容页密钥未被抓"
[ "$rc29" = 1 ] && ok "含密钥 → doctor 非 0 退出" || bad "含密钥仍 0 退出 (rc=$rc29)"
# FP 豁免: skills/ 子树里作为检测器/示例出现的 token 形态不误报
T29B="$(mktemp -d)/i"; mkdir -p "$T29B"; cp -R "$ENGINE/examples/minimal/." "$T29B/"
printf '\n示例密钥 ghp_0123456789abcdefghij0123 仅作说明\n' >> "$T29B/skills/hello-note/SKILL.md"
expect_rc 0 "skills/ 内 token 形态不误报（检测器/示例豁免）" python3 "$DOC" "$T29B"

echo "== 30) 密钥扫描: privacy:sensitive zone（memory/）命中时 ERROR 额外标注其敏感 =="
T30="$(mktemp -d)/i"; mkdir -p "$T30"; cp -R "$ENGINE/template/." "$T30/"
printf -- '---\ntitle: L\ncreated: 2026-01-01\nupdated: 2026-01-01\ntype: note\n---\n# L\n泄漏 AKIA0000000000000000 here\n' > "$T30/memory/about-owner/leak.md"
OUT30="$(python3 "$DOC" "$T30" 2>&1)"
printf '%s' "$OUT30" | grep "疑似密钥" | grep -q "sensitive" && ok "sensitive zone 内密钥 ERROR 额外标注其敏感" || bad "sensitive zone 未额外标注"

echo "== 31) collections upsert: 按 id 幂等（同 id 两次→1 行；新 id→累加；改既有不增行）=="
CSV="$(mktemp -d)/c/data.csv"
python3 "$COLL" upsert --csv "$CSV" --field id=ripgrep --field name=ripgrep --apply >/dev/null 2>&1
python3 "$COLL" upsert --csv "$CSV" --field id=ripgrep --field name=ripgrep --apply >/dev/null 2>&1
n="$(python3 "$COLL" count --csv "$CSV")"; [ "$n" = 1 ] && ok "同 id upsert 两次仍 1 行（幂等去重）" || bad "upsert 非幂等 (got $n)"
python3 "$COLL" upsert --csv "$CSV" --field id=fd --field name=fd --apply >/dev/null 2>&1
n2="$(python3 "$COLL" count --csv "$CSV")"; [ "$n2" = 2 ] && ok "新 id upsert → 累加到 2 行" || bad "新 id 未累加 (got $n2)"
python3 "$COLL" upsert --csv "$CSV" --field id=fd --field category=cli --apply >/dev/null 2>&1
n3="$(python3 "$COLL" count --csv "$CSV")"; [ "$n3" = 2 ] && ok "改既有 id（加字段）不新增行" || bad "改行误增 (got $n3)"

echo "== 32) doctor 正向触发: count-drift / orphan / 断链(basename) / frontmatter 缺失 都真的报 ERROR =="
T32="$(mktemp -d)/i"; mkdir -p "$T32"; cp -R "$ENGINE/examples/minimal/." "$T32/"
python3 - "$T32/collections/tools/tools.md" <<'PY'
import sys; p=sys.argv[1]; t=open(p).read(); open(p,'w').write(t.replace("**5** 条","**99** 条"))
PY
printf -- '---\ntitle: Lonely\ncreated: 2026-01-01\nupdated: 2026-01-01\ntype: concept\n---\n# Lonely\n[[git]] [[markdown]]\n' > "$T32/knowledge/lonely.md"   # 无入链 → 孤儿
printf '\n坏链 [[no-such-basename-xyz]]\n' >> "$T32/knowledge/git.md"                                                            # basename 断链
printf '# NoFM\n[[git]] [[markdown]]\n' > "$T32/knowledge/nofm.md"                                                              # 无 frontmatter
OUT32="$(python3 "$DOC" "$T32" 2>&1)"; rc32=$?
printf '%s' "$OUT32" | grep -q "计数漂移"                  && ok "count-drift 正向触发" || bad "count-drift 未触发"
printf '%s' "$OUT32" | grep -q "孤儿.*lonely"              && ok "orphan 正向触发"      || bad "orphan 未触发"
printf '%s' "$OUT32" | grep -q "断链.*no-such-basename-xyz" && ok "basename 断链正向触发" || bad "basename 断链未触发"
printf '%s' "$OUT32" | grep -q "frontmatter 缺失.*nofm"     && ok "frontmatter 缺失正向触发" || bad "frontmatter 缺失未触发"
[ "$rc32" = 1 ] && ok "有 ERROR → rc=1" || bad "有 ERROR 仍非 1 (rc=$rc32)"

echo "== 33) meta: 真实 migrations/ 链连续且终止于 ENGINE_VERSION（防 bump 版本却不加迁移）=="
python3 - "$ENGINE" <<'PY'
import sys,os,re,glob
eng=sys.argv[1]; ev=open(os.path.join(eng,"ENGINE_VERSION")).read().strip()
migs=[]
for mf in sorted(glob.glob(eng+"/migrations/*/migration.yaml")):
    t=open(mf).read()
    migs.append((re.search(r'from_version:\s*"?([\d.]+)',t).group(1),
                 re.search(r'to_version:\s*"?([\d.]+)',t).group(1)))
key=lambda v: tuple(int(x) for x in v.split("."))
migs.sort(key=lambda m: key(m[0]))
contiguous=all(migs[i][1]==migs[i+1][0] for i in range(len(migs)-1))
sys.exit(0 if (migs and contiguous and migs[-1][1]==ev) else 1)
PY
rc33=$?; [ "$rc33" = 0 ] && ok "migrations 链连续 + max(to)==ENGINE_VERSION($(cat "$ENGINE/ENGINE_VERSION"))" || bad "迁移链断裂或未抵达 ENGINE_VERSION (rc=$rc33)"

echo "== 34) meta: doctor 硬编码的 required 列表与 schema 的 required 一致（防契约漂移）=="
python3 - "$ENGINE" <<'PY'
import sys,os,re
eng=sys.argv[1]
def sch_req(p):
    m=re.search(r'(?m)^required:\s*\[(.*?)\]', open(p).read())
    return set(x.strip() for x in m.group(1).split(",")) if m else set()
doc=open(os.path.join(eng,"skills/substrate-doctor/doctor.py")).read()
dm=set(x.strip().strip('"\'') for x in re.search(r'MANIFEST_REQUIRED\s*=\s*\[(.*?)\]',doc).group(1).split(","))
dz=set(re.findall(r'"([a-z_]+)"', re.search(r'for k in \((.*?)\) if k not in present',doc).group(1))) | {"id"}
sm=sch_req(os.path.join(eng,"schemas/skill-manifest.schema.yaml"))
zn=sch_req(os.path.join(eng,"schemas/zone.schema.yaml"))
ok=(dm==sm) and (dz==zn)
if not ok:
    print("manifest: doctor",dm,"!= schema",sm); print("zone: doctor",dz,"!= schema",zn)
sys.exit(0 if ok else 1)
PY
rc34=$?; [ "$rc34" = 0 ] && ok "doctor required 列表 == schema required（无漂移）" || bad "doctor 与 schema 的 required 漂移 (rc=$rc34)"

echo "== 35) doctor: vendored skill 引擎版本 vs 实例 schema 版本错位 → WARN（不拦路）=="
T35="$(mktemp -d)/i"; mkdir -p "$T35"; cp -R "$ENGINE/examples/minimal/." "$T35/"   # SUBSTRATE_VERSION=0.2.0
printf '0.3.0\n' > "$T35/skills/.engine-version"   # 模拟 --refresh 到 0.3.0 但没 migrate
OUT35="$(python3 "$DOC" "$T35" 2>&1)"; rc35=$?
printf '%s' "$OUT35" | grep -q "引擎版本错位" && ok "版本错位 → WARN" || bad "版本错位未 WARN"
[ "$rc35" = 0 ] && ok "版本错位是 WARN 不改退出码(rc=0)" || bad "版本错位误报为 ERROR (rc=$rc35)"
printf '0.2.0\n' > "$T35/skills/.engine-version"   # 与 SUBSTRATE_VERSION 对齐
python3 "$DOC" "$T35" 2>&1 | grep -q "引擎版本错位" && bad "版本对齐仍误报错位" || ok "版本对齐不误报"

echo "== 36) meta: migrations/INDEX.md 与磁盘上的迁移目录一一对应（防 INDEX 漂移）=="
python3 - "$ENGINE" <<'PY'
import sys,os,re,glob
eng=sys.argv[1]
dirs={os.path.basename(os.path.dirname(p)) for p in glob.glob(eng+"/migrations/*/migration.yaml")}
idx=open(os.path.join(eng,"migrations/INDEX.md")).read()
listed={d for d in dirs if d in idx}                       # 每个磁盘迁移 id 都出现在 INDEX
mentioned=set(re.findall(r'\b(\d{4}-[a-z0-9-]+)\b', idx))  # INDEX 提到的 id 形态串都是真实目录
sys.exit(0 if (dirs==listed and mentioned<=dirs) else 1)
PY
rc36=$?; [ "$rc36" = 0 ] && ok "INDEX 与磁盘迁移目录一致" || bad "INDEX 与磁盘迁移漂移 (rc=$rc36)"

echo "== 37) sync: deprecated/superseded skill 不装 + 从 target 移除既有（旧 skill 退役）=="
SR="$(mktemp -d)/skills"; mkdir -p "$SR/keepme" "$SR/oldone"
printf -- '---\nname: keepme\ntarget_runtimes: [all]\nrisk_level: low\n---\nkeep\n' > "$SR/keepme/SKILL.md"
printf -- '---\nname: oldone\ntarget_runtimes: [all]\nrisk_level: low\ndeprecated: true\nsuperseded_by: keepme\n---\nold\n' > "$SR/oldone/SKILL.md"
TGT="$(mktemp -d)/t"; mkdir -p "$TGT/oldone"; printf 'stale\n' > "$TGT/oldone/SKILL.md"   # 模拟之前装过
OUT37="$(python3 "$SYNC" --src "$SR" --target "$TGT" --runtime claude-code --apply 2>&1)"
[ -d "$TGT/keepme" ] && ok "未退役 skill 正常安装" || bad "未退役 skill 没装"
[ -d "$TGT/oldone" ] && bad "已退役 skill 未从 target 移除" || ok "已退役 skill 从 target 移除"
printf '%s' "$OUT37" | grep -qi "retire\|退役\|superseded" && ok "退役有提示" || bad "退役无提示"

echo "== 38) doctor fleet: >1 migration_leader → ERROR；多机无 leader → WARN =="
T38="$(mktemp -d)/i"; mkdir -p "$T38"; cp -R "$ENGINE/template/." "$T38/"
printf '# fleet\n\n```yaml\ndevices:\n  - id: a\n    role: main-dev\n    migration_leader: true\n  - id: b\n    role: headless-dev\n    migration_leader: true\n```\n' > "$T38/fleet/README.md"
OUT38="$(python3 "$DOC" "$T38" 2>&1)"; rc38=$?
printf '%s' "$OUT38" | grep -q "migration_leader" && ok ">1 migration_leader 被抓" || bad ">1 leader 未抓"
[ "$rc38" = 1 ] && ok ">1 leader → rc=1(ERROR)" || bad ">1 leader 未致 rc1 (rc=$rc38)"
printf '# fleet\n\n```yaml\ndevices:\n  - id: a\n    role: main-dev\n  - id: b\n    role: headless-dev\n```\n' > "$T38/fleet/README.md"
python3 "$DOC" "$T38" 2>&1 | grep -q "无 migration_leader" && ok "多机无 leader → WARN" || bad "多机无 leader 未 WARN"
expect_rc 0 "多机无 leader 是 WARN 不致 rc1" python3 "$DOC" "$T38"

echo "== 39) doctor: zones.md 有 yaml 块却解析不出任何 zone → WARN（不静默漏检）=="
T39="$(mktemp -d)/i"; mkdir -p "$T39"; cp -R "$ENGINE/examples/minimal/." "$T39/"
python3 - "$T39/governance/zones.md" <<'PY'
import sys,re; p=sys.argv[1]; t=open(p).read()
m=re.search(r'```yaml\n(.*?)```',t,re.S); blk=m.group(1).replace('- id:','* id:')   # 破坏 `- id:` 形态 → 解析不出
open(p,'w').write(t[:m.start(1)]+blk+t[m.end(1):])
PY
python3 "$DOC" "$T39" 2>&1 | grep -q "解析不出" && ok "zones 解析不出条目 → WARN" || bad "zones 解析失败被静默"

echo "== 40) substrate-runtime-context: 小抄生成（各区 Agent Packet + about-owner + 路由表 + 体积护栏）=="
RCX="$ENGINE/skills/substrate-runtime-context/render-context.py"
expect_rc 2 "无效路径 → rc=2" python3 "$RCX" /no/such/dir
T40="$(mktemp -d)/inst"; mkdir -p "$T40"; cp -R "$ENGINE/template/." "$T40/"
mkdir -p "$T40/skills/substrate-todo"; cp "$ENGINE/skills/substrate-todo/SKILL.md" "$T40/skills/substrate-todo/SKILL.md"
printf -- '---\ntitle: 饮食偏好\ntype: memory\nowner: <主人>\ncreated: 2026-01-01\nupdated: 2026-01-01\n---\n主人吃素，咖啡不加糖。\n' > "$T40/memory/about-owner/prefs.md"
OUT40="$(python3 "$RCX" "$T40" 2>/dev/null)"
printf '%s' "$OUT40" | grep -q "substrate-memory" && ok "纳入各区 Agent Packet" || bad "缺 Agent Packet"
printf '%s' "$OUT40" | grep -q "主人吃素" && ok "纳入 about-owner 记忆正文" || bad "缺 about-owner 正文"
printf '%s' "$OUT40" | grep -q "type: memory" && bad "记忆 frontmatter 泄漏" || ok "记忆 frontmatter 已剥离"
printf '%s' "$OUT40" | grep -q "加个待办" && ok "路由表从 skill description 派生" || bad "缺路由表触发词"
printf '%s' "$OUT40" | grep -q "先提议后写\|绝不擅自写库" && ok "房规（主动捕获先提议）已含" || bad "缺房规"
# about-owner 的 README 索引页不当作记忆正文混入
printf '%s' "$OUT40" | grep -q "命名约定（引擎中立）" && bad "about-owner/README 被误当记忆" || ok "about-owner/README 不混入记忆段"
# 体积护栏：超上限只 stderr 告警、stdout 仍出内容、rc=0
{ printf -- '---\ntitle: big\ntype: memory\n---\n'; python3 -c "print('主人偏好 '*4000)"; } > "$T40/memory/about-owner/big.md"
ERR40="$(python3 "$RCX" "$T40" 2>&1 >/dev/null)"; rc40=$?
printf '%s' "$ERR40" | grep -q "体积" && ok "超体积上限 → stderr 告警" || bad "超体积无告警"
[ "$rc40" = 0 ] && ok "超体积仍 rc=0（只告警不失败）" || bad "超体积误致非0 (rc=$rc40)"
python3 "$RCX" "$T40" 2>/dev/null | grep -q "主人偏好" && ok "超体积 stdout 不截断" || bad "超体积 stdout 被破坏"
# 缺区容忍：examples/minimal 没有 todo/memory 区也不崩、不报错
expect_rc 0 "缺 todo/memory 区也正常生成（examples/minimal）" python3 "$RCX" "$ENGINE/examples/minimal"

echo "== 41) doctor: about-owner 体积超阈值 → WARN（防常驻小抄膨胀，不改退出码）=="
T41="$(mktemp -d)/inst"; mkdir -p "$T41"; cp -R "$ENGINE/template/." "$T41/"
{ printf -- '---\ntitle: big\ntype: memory\nowner: x\ncreated: 2026-01-01\nupdated: 2026-01-01\n---\n见 [[prefs]] 与 [[owner]]。\n'; python3 -c "print('主人偏好细节 '*1500)"; } > "$T41/memory/about-owner/big.md"
printf -- '---\ntitle: p\ntype: memory\nowner: x\ncreated: 2026-01-01\nupdated: 2026-01-01\n---\n小事实。见 [[big]] 与 [[owner]]。\n' > "$T41/memory/about-owner/prefs.md"
printf -- '---\ntitle: o\ntype: memory\nowner: x\ncreated: 2026-01-01\nupdated: 2026-01-01\n---\n主人。见 [[big]] 与 [[prefs]]。\n' > "$T41/memory/about-owner/owner.md"
printf '\n- [[big]]\n- [[prefs]]\n- [[owner]]\n' >> "$T41/memory/about-owner/README.md"
python3 "$DOC" "$T41" 2>&1 | grep -q "about-owner 体积" && ok "about-owner 膨胀 → WARN" || bad "about-owner 膨胀未 WARN"
expect_rc 0 "about-owner 体积是 WARN 不致 rc1" python3 "$DOC" "$T41"
# 小 about-owner 不误报
python3 "$DOC" "$ENGINE/template" 2>&1 | grep -q "about-owner 体积" && bad "小 about-owner 误报体积" || ok "小 about-owner 不误报"

echo
echo "==== 结果: $PASS passed, $FAIL failed, $SKIP skipped ===="
[ "$FAIL" = 0 ]
