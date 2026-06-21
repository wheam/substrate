#!/usr/bin/env python3
"""substrate-intake gate — 自动回流 skill 的守门（零依赖，python3 标准库）。

读一个 skill 文件夹的 SKILL.md frontmatter，**按 capabilities 推断**风险，决定：
  - promote = 可自动晋升（只读写 markdown，无危险 capability）。
  - audit   = 转人工 audit（含 shell/system/network/install/secrets/
              modify-skills/modify-governance 任一危险 capability）。
  - error   = 没法判（缺 SKILL.md / 缺 frontmatter / 缺 name）。

★ 关键纪律：**不信任 skill 自报的 risk_level**——风险一律由 capabilities 重推。
  自报 risk_level 只用于「自报 vs 实判」是否矛盾的提示，不参与决策。

用法:
  python3 gate.py <skill 文件夹路径>     # 如 .../skills/_incoming/some-skill

退出码:
  0 = promote（可自动晋升）
  1 = audit（转人工）
  2 = error（输入坏：缺文件夹/缺 SKILL.md/缺 frontmatter/缺 name）

设计约束（对齐引擎其它脚本）:
  - 零依赖、CWD 无关（路径全参数化）、坏输入优雅退出不崩。
  - 容忍 BOM / 前导空行 / frontmatter 内行尾注释 / 列表项间空行或注释行。
  - **fail-closed**：任何无法**完整且无歧义**解析为「纯读写 markdown」的情形都倒向 audit，
    绝不误放危险件——包括 capabilities 重复声明、块内夹非列表行、写了键却无项等。
"""
import sys, os, re

# 任一出现即 fail-closed → audit。与 governance/admission.md、skill-manifest.schema 对齐。
DANGEROUS = {
    "shell", "system", "network", "install",
    "secrets", "modify-skills", "modify-governance",
}
# 已知安全的 capability 白名单（只读写 markdown 一类）。未知 capability 一律视为危险。
# 词表见 governance/admission.md「capability 词表」与 skills/substrate-intake/SKILL.md。
SAFE = {"read", "write", "read-markdown", "write-markdown", "markdown"}


def read_text(path):
    try:
        return open(path, encoding="utf-8-sig", errors="replace").read()
    except Exception:
        return None


def frontmatter(text):
    """抽顶部 YAML frontmatter 体；容忍 BOM(读时已去)/前导空行。无则返回 None。"""
    m = re.match(r"\s*---\s*\n(.*?)\n---", text, re.S)
    return m.group(1) if m else None


def scalar(fm, key):
    """读单值标量字段（去行尾 # 注释、去引号）。无则 None。"""
    m = re.search(rf"(?m)^{key}:[ \t]*(.+?)[ \t]*$", fm)
    if not m:
        return None
    v = m.group(1)
    v = re.sub(r"\s+#.*$", "", v).strip()   # 行尾注释
    return v.strip("'\"") or None


def parse_caplist(fm, key):
    """解析 capabilities 列表，**fail-closed**。返回 (items, status)，
    status ∈ {ok, absent, empty, malformed, duplicate}:
      - inline `[a, b]`（含空 `[]`）→ ok。
      - 块式 `- a` 多行：容忍行间**空行/注释**，收集**全部**项；
        遇到比 key 更深缩进但不是 `- 项` 的行（畸形）→ malformed；块内零项 → empty。
      - 同名 key 出现一个以上 → duplicate（真实 YAML 后者覆盖；守门不赌，转人工）。
    旧实现的 bug：块内一个空行或注释会让正则停在那里、丢掉后续 `- shell`，
    把危险件误判为安全 → fail-OPEN。本实现逐行收集，杜绝该绕过。"""
    if len(re.findall(rf"(?m)^[ \t]*{key}[ \t]*:", fm)) > 1:
        return [], "duplicate"
    # 内联 [a, b]（容忍多行流式 [a,\n b]）
    m = re.search(rf"(?m)^[ \t]*{key}[ \t]*:[ \t]*\[(.*?)\]", fm, re.S)
    if m:
        return [x.strip().strip("'\"") for x in m.group(1).split(",") if x.strip()], "ok"
    # 块式 header
    m = re.search(rf"(?m)^([ \t]*){key}[ \t]*:[ \t]*$", fm)
    if not m:
        return [], "absent"
    key_indent = len(m.group(1).replace("\t", "    "))
    out = []
    for line in fm[m.end():].split("\n"):
        if line.strip() == "":
            continue                              # 空行：容忍，块未结束
        if line.lstrip().startswith("#"):
            continue                              # 注释行：容忍
        indent = len(line[:len(line) - len(line.lstrip())].replace("\t", "    "))
        if indent <= key_indent:
            break                                 # 退缩进 → 块结束
        mi = re.match(r"-[ \t]*(.+)$", line.strip())
        if not mi:
            return out, "malformed"               # 更深缩进但非列表项 → 畸形 → fail-closed
        val = re.sub(r"\s+#.*$", "", mi.group(1)).strip().strip("'\"")
        if val:
            out.append(val)
    return (out, "ok") if out else (out, "empty")


def classify(caps):
    """按 capabilities 判风险（不看自报 risk_level）。
    返回 (decision, dangerous_hits, unknown_hits)。
    fail-closed：危险命中 → audit；出现任何非白名单 capability → audit。"""
    norm = [c.strip().lower() for c in caps if c.strip()]
    dangerous = sorted({c for c in norm if c in DANGEROUS})
    unknown = sorted({c for c in norm if c not in DANGEROUS and c not in SAFE})
    if dangerous or unknown:
        return "audit", dangerous, unknown
    return "promote", [], []


def main(argv):
    if len(argv) != 2:
        print("用法: python3 gate.py <skill 文件夹路径>")
        return 2
    skill_dir = os.path.abspath(argv[1])
    name_hint = os.path.basename(skill_dir.rstrip(os.sep))

    if not os.path.isdir(skill_dir):
        print(f"[ERROR] {name_hint}: 不是文件夹: {skill_dir}")
        return 2

    sk = os.path.join(skill_dir, "SKILL.md")
    if not os.path.isfile(sk):
        print(f"[ERROR] {name_hint}: 缺 SKILL.md（不是合法 skill 文件夹）")
        return 2

    text = read_text(sk)
    if text is None:
        print(f"[ERROR] {name_hint}: SKILL.md 无法读取（非 UTF-8/损坏）")
        return 2

    fm = frontmatter(text)
    if fm is None:
        # 没 manifest = 无法判定来源/能力 → fail-closed 到 error（人来看），不静默放行。
        print(f"[ERROR] {name_hint}: SKILL.md 缺 frontmatter（manifest）——无法判风险，转人工")
        return 2

    name = scalar(fm, "name") or name_hint
    if not scalar(fm, "name"):
        print(f"[ERROR] {name}: manifest 缺必填字段 name，转人工")
        return 2

    caps, status = parse_caplist(fm, "capabilities")
    declared = (scalar(fm, "risk_level") or "").lower() or None

    shown = caps if caps else ("[] (显式空)" if status == "ok" else f"({status})")
    print(f"substrate-intake gate: {name}")
    print(f"  capabilities: {shown}")
    print(f"  自报 risk_level: {declared or '(未声明)'}  (仅供参考，不参与判定)")

    # fail-closed：任何无法「完整、无歧义」判为纯安全的情形 → audit（绝不误放危险件）。
    if status == "absent":
        print("  → AUDIT（转人工）：未声明 capabilities，无法判定安全。要自动晋升须显式写 `capabilities: []`（或安全能力）。")
        return 1
    if status == "duplicate":
        print("  → AUDIT（转人工）：capabilities 键重复声明——真实 YAML 后者覆盖，守门不赌，转人工。")
        return 1
    if status == "malformed":
        print("  → AUDIT（转人工）：capabilities 列表格式异常（块内夹非列表项行等），无法可靠解析——fail-closed。")
        return 1
    if status == "empty":
        print("  → AUDIT（转人工）：写了 capabilities 键但无任何项（YAML 解析为 null，非空列表）——fail-closed。要自动晋升请写 `capabilities: []`。")
        return 1

    decision, dangerous, unknown = classify(caps)
    if decision == "promote":
        print("  → PROMOTE（可自动晋升）：无危险 capability，判为只读写 markdown 一类。")
        if declared in ("medium", "high"):
            print(f"    注意：自报 {declared} 但实判为低风险——已按 capabilities 判。")
        return 0

    # audit
    reasons = []
    if dangerous:
        reasons.append(f"危险 capability: {', '.join(dangerous)}")
    if unknown:
        reasons.append(f"未知 capability(白名单外，按危险处理): {', '.join(unknown)}")
    print("  → AUDIT（转人工）：" + "；".join(reasons))
    if declared in (None, "low"):
        print(f"    注意：自报 {declared or '未声明'} 但 capabilities 含危险位——这正是不信任自报值的理由。")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
