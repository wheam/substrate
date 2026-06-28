#!/usr/bin/env python3
"""substrate-runtime-context — 生成「常驻上下文小抄」（零依赖，python3 标准库）。

用法:  python3 render-context.py [INSTANCE_ROOT]   (默认当前目录)
输出:  一段 markdown「常驻上下文」到 stdout —— 由 runtime 的 session-start hook 灌进上下文。
退出码: 0 = 成功; 2 = 调用错误（路径不对）。

设计约束（同引擎其它脚本，见 docs/BUILD-PLAN.md §15）:
  - 不假设 PyYAML：frontmatter 用受限子集正则剥离。
  - 小抄是【定量】的：只拼各区 Agent Packet（摘要）+ about-owner 记忆 + 路由表 + 房规，
    永不拼全库。超体积上限只告警（stderr），不改 stdout、不失败。
"""
import sys, os, glob, re

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))

# 小抄体积上限（字符）。超了只告警、不截断、不失败——提醒主人去精简 about-owner。
# 约 12k 字符 ≈ 3–4k token，是「定量小抄」的合理护栏。可用环境变量覆盖。
DEFAULT_MAX_CHARS = 12000


def read_text(p):
    try:
        return open(p, encoding="utf-8-sig", errors="replace").read()
    except Exception:
        return None


def strip_frontmatter(text):
    """剥掉顶部 `--- … ---` YAML frontmatter（不假设 PyYAML，只按分隔符切）。"""
    m = re.match(r"\s*---\s*\n.*?\n---[ \t]*\n?", text, re.S)
    return text[m.end():] if m else text


def fm_field(text, key):
    """读 frontmatter 里的标量字段（剥引号）。无则 None。"""
    m = re.match(r"\s*---\s*\n(.*?)\n---", text, re.S)
    if not m:
        return None
    f = re.search(r"(?m)^%s:[ \t]*(.+?)[ \t]*$" % re.escape(key), m.group(1))
    return f.group(1).strip().strip("'\"") if f else None


def read_core(root):
    """核心摘要 memory/about-owner/_core.md 的正文（永远整段进小抄）。无则 None。"""
    t = read_text(os.path.join(root, "memory", "about-owner", "_core.md"))
    if not t:
        return None
    body = strip_frontmatter(t).strip()
    return body or None


def memory_index(root):
    """其余分类记忆页的一行索引（summary→title→slug；跳过 README 与 `_*` 结构页）。

    分类页全文不进小抄——只列目录，agent 需要细节时用 substrate-memory 现读对应页。
    """
    out = []
    base = os.path.join(root, "memory", "about-owner")
    for p in sorted(glob.glob(os.path.join(base, "*.md"))):
        name = os.path.basename(p)
        if name.lower() == "readme.md" or name.startswith("_"):
            continue
        t = read_text(p)
        if not t:
            continue
        slug = os.path.splitext(name)[0]
        desc = fm_field(t, "summary") or fm_field(t, "title") or slug
        out.append("- [[%s]] — %s" % (slug, desc))
    return out


def agent_packet(text):
    """抽 README 顶部的 `> **Agent Packet**` 引用块（连续 `>` 行）。无则 None。"""
    lines = text.split("\n")
    for i, ln in enumerate(lines):
        if ln.lstrip().startswith(">") and "Agent Packet" in ln:
            block = []
            for ln2 in lines[i:]:
                if ln2.lstrip().startswith(">"):
                    block.append(ln2)
                else:
                    break
            return "\n".join(block)
    return None


def zone_packets(root):
    """扫描实例内所有 README.md，收集带 Agent Packet 的，按路径排序（确定性）。"""
    out = []
    for p in sorted(glob.glob(os.path.join(root, "**", "README.md"), recursive=True)):
        t = read_text(p)
        if not t:
            continue
        pkt = agent_packet(t)
        if pkt:
            out.append(pkt)
    return out


def skill_description(text):
    """从 SKILL.md frontmatter 读 `description`（去引号）。无则 None。"""
    m = re.match(r"\s*---\s*\n(.*?)\n---", text, re.S)
    if not m:
        return None
    d = re.search(r"(?m)^description:[ \t]*(.+?)[ \t]*$", m.group(1))
    if not d:
        return None
    return d.group(1).strip().strip("'\"").strip()


def router(root):
    """扫 skills/<name>/SKILL.md，按 name+description 拼「触发→skill」表（确定性排序）。

    只收 `substrate-*`（知识库维护 skill）——本小抄是「怎么用知识库」的路由，
    runtime 里的自定义 skill（curio / operating-* / 各类 research…）有自己的触发，
    不属于这里，纳入只会膨胀小抄、稀释信号。
    """
    rows = []
    for p in sorted(glob.glob(os.path.join(root, "skills", "*", "SKILL.md"))):
        name = os.path.basename(os.path.dirname(p))
        if not name.startswith("substrate-"):
            continue
        t = read_text(p)
        if not t:
            continue
        desc = skill_description(t)
        if desc:
            rows.append("- **%s** — %s" % (name, desc))
    return rows


def render(root):
    parts = ["# Substrate 常驻上下文（自动生成，勿手改）"]
    core = read_core(root)
    if core:
        parts.append("## 关于主人（核心）")
        parts.append(core)
    idx = memory_index(root)
    if idx:
        parts.append("## 关于主人（记忆目录，需要细节时用 substrate-memory 读对应页）")
        parts.append("\n".join(idx))
    packets = zone_packets(root)
    if packets:
        parts.append("## 库里有什么（各区速览）")
        parts.extend(packets)
    rows = router(root)
    if rows:
        parts.append("## 何时用哪个 skill（路由表）")
        parts.append("\n".join(rows))
    house = read_text(os.path.join(SKILL_DIR, "house-rules.md"))
    if house and house.strip():
        parts.append(house.strip())
    return "\n\n".join(parts) + "\n"


def main(argv):
    root = argv[1] if len(argv) > 1 else "."
    if not os.path.isdir(root):
        sys.stderr.write("render-context: 路径不是目录: %s\n" % root)
        return 2
    out = render(root)
    try:
        limit = int(os.environ.get("SUBSTRATE_CONTEXT_MAX_CHARS", DEFAULT_MAX_CHARS))
    except ValueError:
        limit = DEFAULT_MAX_CHARS
    if limit > 0 and len(out) > limit:
        sys.stderr.write(
            "render-context: ⚠ 小抄体积 %d 字符，超过上限 %d —— "
            "建议精简 memory/about-owner/（小抄应保持定量）。\n" % (len(out), limit)
        )
    sys.stdout.write(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
