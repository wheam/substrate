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
  - 容忍 BOM / 前导空行 / frontmatter 内行尾注释。
  - **fail-closed**：任何无法确定为「纯读写 markdown」的情形都倒向 audit，绝不误放危险件。
"""
import sys, os, re

# 任一出现即 fail-closed → audit。与 governance/admission.md、skill-manifest.schema 对齐。
DANGEROUS = {
    "shell", "system", "network", "install",
    "secrets", "modify-skills", "modify-governance",
}
# 已知安全的 capability 白名单（只读写 markdown 一类）。未知 capability 一律视为危险。
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


def listfield(fm, key):
    """读列表字段：支持 [a, b] 内联式与多行 `- a` 块式。无则 []。"""
    m = re.search(rf"(?m)^{key}:[ \t]*\[(.*?)\]", fm, re.S)   # re.S：容忍多行 [a,\n b] 流式列表
    if m:
        return [x.strip().strip("'\"") for x in m.group(1).split(",") if x.strip()]
    m = re.search(rf"(?m)^{key}:[ \t]*\n((?:[ \t]*-[ \t]*.+\n?)+)", fm)
    if m:
        out = []
        for line in m.group(1).splitlines():
            line = re.sub(r"^[ \t]*-[ \t]*", "", line)
            line = re.sub(r"\s+#.*$", "", line).strip().strip("'\"")
            if line:
                out.append(line)
        return out
    return []


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

    cap_present = re.search(r"(?m)^[ \t]*capabilities[ \t]*:", fm) is not None
    explicit_empty = re.search(r"(?m)^[ \t]*capabilities[ \t]*:[ \t]*\[[ \t]*\][ \t]*$", fm) is not None
    caps = listfield(fm, "capabilities")
    declared = (scalar(fm, "risk_level") or "").lower() or None

    print(f"substrate-intake gate: {name}")
    print(f"  capabilities: {caps if caps else ('[] (显式空)' if explicit_empty else '(未声明/无法解析)')}")
    print(f"  自报 risk_level: {declared or '(未声明)'}  (仅供参考，不参与判定)")

    # fail-closed：能力声明缺失或无法解析 → 一律 audit（绝不误放危险件）。
    if not cap_present:
        print("  → AUDIT（转人工）：未声明 capabilities，无法判定安全。要自动晋升须显式写 `capabilities: []`（或安全能力）。")
        return 1
    if not caps and not explicit_empty:
        print("  → AUDIT（转人工）：capabilities 无法解析（标量/多行格式异常等）——fail-closed，转人工。")
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
