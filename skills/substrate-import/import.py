#!/usr/bin/env python3
"""substrate-import — 批量把已有 markdown 搬进一个新 Substrate 实例（零依赖，python3 标准库）。

用法:
  python3 import.py --source <来源目录> --instance <实例根> \
                    [--adapter generic-md|obsidian] [--zone knowledge] \
                    [--date YYYY-MM-DD] [--type note] [--apply]

默认 **dry-run**：只扫描来源、为每个 .md 提议目标 zone/路径，打印映射计划，不动任何文件。
加 --apply 才真正：拷文件到目标 zone + 给缺 frontmatter 的补最小 frontmatter(title/created/updated/type)。
幂等：目标已存在的文件跳过（重跑不重复拷、不二次补 frontmatter）。

设计约束（见引擎 docs/BUILD-PLAN.md §10）:
  - 零依赖、CWD 无关（路径参数化）、坏输入优雅退出不崩。
  - 副作用默认 dry-run；分类是判断（落哪 zone/剔敏感位），脚本只给保守默认提议，
    精细分类与审批由 substrate-intake + 人完成。
  - 日期由 --date 传入或留占位符（不用 wall-clock 即时取值，保证可复现）。
  - 模糊/可疑内容不批量塞库：标 SKIP/REVIEW，留给人审批，宁缺勿滥。

退出码: 0 = 正常; 2 = 调用错误（路径不对/来源不存在等）。
"""
import sys, os, re, glob, argparse, shutil

DATE_PLACEHOLDER = "YYYY-MM-DD"
# 文件名里出现这些词的，标 REVIEW（疑似敏感/凭据），dry-run 不默认计入计划、--apply 不搬。
SENSITIVE_HINTS = ("secret", "secrets", "credential", "credentials", "password",
                   "passwd", "token", "apikey", "api-key", "api_key", "private-key",
                   ".env", "id_rsa")
# 内容里命中这些模式的，标 REVIEW（可能含密钥/敏感原文）。保守、低误报。
SENSITIVE_CONTENT = [
    re.compile(r"BEGIN[ A-Z]*PRIVATE KEY"),
    re.compile(r"(?i)\b\w*(?:api[_-]?key|secret|password|passwd|token)\w*\s*[:=]\s*\S{6,}"),  # 含 OPENAI_API_KEY=/DATABASE_PASSWORD= 等下划线前缀环境变量
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),                 # AWS access key id 形态
    re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{10,}"),       # slack token 形态
    re.compile(r"\bgh[pousr]_[0-9A-Za-z]{20,}"),         # GitHub token (ghp_/gho_/...)
    re.compile(r"\bgithub_pat_[0-9A-Za-z_]{20,}"),       # GitHub fine-grained PAT
    re.compile(r"\bAIza[0-9A-Za-z_\-]{30,}"),            # Google API key
    re.compile(r"\bsk_live_[0-9A-Za-z]{16,}"),           # Stripe live key
    re.compile(r"\beyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}"),  # JWT
]


def read_text(p):
    try:
        return open(p, encoding="utf-8-sig", errors="replace").read()
    except Exception:
        return None


def slugify(name):
    """文件名 → 全小写、连字符、无空格的 slug。保留 unicode 文字（中日韩/西里尔等不被剥成 untitled，
    否则多个非 ASCII 名都会坍缩成 untitled 互相撞名而无法导入）。"""
    s = name.lower()
    s = re.sub(r"[\s_]+", "-", s)
    s = re.sub(r"[^\w.\-]", "", s, flags=re.UNICODE)   # 保留 \w（含 unicode 文字/数字），去其余标点
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s or "untitled"


def has_frontmatter(text):
    """是否已有 YAML frontmatter。须是开头的 --- ... ---，且块内至少一行 `key:`
    （否则只是正文开头的 `---` 分隔线/水平线，不是 frontmatter）。"""
    m = re.match(r"\s*---[ \t]*\n(.*?)\n---[ \t]*(?:\n|$)", text or "", re.S)
    if not m:
        return False
    return re.search(r"(?m)^[A-Za-z_][\w-]*[ \t]*:", m.group(1)) is not None


def first_heading_or_name(text, fallback):
    """取首个 markdown 标题作 title；没有就用文件名（去扩展名、连字符转空格）。"""
    for line in (text or "").splitlines():
        m = re.match(r"\s*#{1,6}\s+(.+?)\s*#*\s*$", line)
        if m:
            return m.group(1).strip()
    base = re.sub(r"\.md$", "", fallback, flags=re.I)
    return re.sub(r"[-_]+", " ", base).strip() or "Untitled"


def is_ignored_dir(rel_parts, adapter):
    """来源里要忽略的目录段（点目录；obsidian 额外忽略 .obsidian/.trash）。"""
    for seg in rel_parts:
        if seg.startswith("."):
            return True
        if adapter == "obsidian" and seg in (".obsidian", ".trash"):
            return True
    return False


def sensitive_reason(relpath, text):
    low = relpath.lower()
    for h in SENSITIVE_HINTS:
        if h in low:
            return f"文件名含敏感词 '{h}'"
    head = (text or "")[:20000]   # 只扫前段，省内存
    for pat in SENSITIVE_CONTENT:
        if pat.search(head):
            return "内容疑似含密钥/凭据"
    return None


def scan(source, adapter):
    """扫描来源，返回 [(abs_path, relpath)]，relpath 相对 source、用 / 分隔。"""
    out = []
    for p in sorted(glob.glob(source + "/**/*.md", recursive=True)):
        rp = os.path.relpath(p, source).replace(os.sep, "/")
        parts = rp.split("/")
        if is_ignored_dir(parts[:-1], adapter):
            continue
        out.append((p, rp))
    return out


def propose_target(relpath, zone):
    """为来源里的一个 .md 提议目标相对路径（实例根相对，/ 分隔）。

    保守默认：落到 --zone（默认 knowledge/），保留来源的子目录层级，文件名 slug 化。
    精细分类（四去向 / 拆 skill / 该不该换 zone）是判断，交 substrate-intake + 人。
    """
    parts = relpath.split("/")
    dirs = [slugify(d) for d in parts[:-1]]
    base = parts[-1]
    stem = re.sub(r"\.md$", "", base, flags=re.I)
    fname = slugify(stem) + ".md"
    return "/".join([zone] + dirs + [fname])


def ensure_frontmatter(text, title, date, ctype):
    """若无 frontmatter 则补最小集（title/created/updated/type）；已有则原样返回。"""
    if has_frontmatter(text):
        return text, False
    # title 里的双引号转义，避免破坏 YAML
    safe_title = title.replace('"', '\\"')
    fm = (
        "---\n"
        f'title: "{safe_title}"\n'
        f"created: {date}\n"
        f"updated: {date}\n"
        f"type: {ctype}\n"
        "---\n\n"
    )
    body = text if text is not None else ""
    # 来源若以标题/正文开头，保留；frontmatter 前置
    return fm + body.lstrip("\n"), True


def main():
    ap = argparse.ArgumentParser(description="批量把已有 markdown 搬进 Substrate 实例（默认 dry-run）。")
    ap.add_argument("--source", required=True, help="来源目录（md 文件夹 / obsidian vault）")
    ap.add_argument("--instance", required=True, help="目标 Substrate 实例根目录")
    ap.add_argument("--adapter", default="generic-md", choices=["generic-md", "obsidian"],
                    help="来源适配器（默认 generic-md）")
    ap.add_argument("--zone", default="knowledge", help="默认落入的 zone（默认 knowledge）")
    ap.add_argument("--date", default=DATE_PLACEHOLDER,
                    help="补 frontmatter 用的日期 YYYY-MM-DD；不传则留占位符 " + DATE_PLACEHOLDER)
    ap.add_argument("--type", dest="ctype", default="note",
                    help="补 frontmatter 的 type 字段默认值（默认 note）")
    ap.add_argument("--apply", action="store_true", help="真正执行（默认 dry-run）")
    a = ap.parse_args()

    source = os.path.abspath(a.source)
    instance = os.path.abspath(a.instance)
    if not os.path.isdir(source):
        print(f"substrate-import: --source 不是目录: {source}"); return 2
    if not os.path.isdir(instance):
        print(f"substrate-import: --instance 不是目录: {instance}"); return 2
    if a.date != DATE_PLACEHOLDER and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", a.date):
        print(f"substrate-import: --date 须是 YYYY-MM-DD: {a.date}"); return 2
    # 防 --zone 含 ../ 把文件写到实例根之外
    zone_abs = os.path.abspath(os.path.join(instance, *a.zone.split("/")))
    if os.path.commonpath([instance, zone_abs]) != instance:
        print(f"substrate-import: --zone 越出实例根，拒绝: {a.zone}"); return 2

    items = scan(source, a.adapter)
    dry = not a.apply
    zone_dir = os.path.join(instance, *a.zone.split("/"))

    plan_new, plan_skip, plan_review = [], [], []
    seen_targets = {}   # 目标相对路径 -> 来源 relpath（查来源内撞名）

    for abspath, relpath in items:
        text = read_text(abspath)
        reason = sensitive_reason(relpath, text)
        target_rel = propose_target(relpath, a.zone)
        target_abs = os.path.join(instance, *target_rel.split("/"))
        needs_fm = not has_frontmatter(text)
        title = first_heading_or_name(text, os.path.basename(relpath))

        if reason:
            plan_review.append((relpath, reason)); continue
        if target_rel in seen_targets:
            plan_review.append((relpath, f"目标撞名 {target_rel}（已被 {seen_targets[target_rel]} 占）—需人工区分")); continue
        seen_targets[target_rel] = relpath
        if os.path.exists(target_abs):
            plan_skip.append((relpath, target_rel, "目标已存在（幂等跳过）")); continue
        plan_new.append({"src": abspath, "relpath": relpath, "target_rel": target_rel,
                         "target_abs": target_abs, "needs_fm": needs_fm, "title": title})

    # ── 打印映射计划 ──
    print(f"substrate-import  adapter={a.adapter}  source={source}")
    print(f"                  instance={instance}  zone={a.zone}  mode={'DRY-RUN' if dry else 'APPLY'}")
    print(f"  扫描到 {len(items)} 个 .md")
    for p in plan_new:
        fmnote = " + 补 frontmatter" if p["needs_fm"] else " (已有 frontmatter)"
        print(f"  NEW     {p['relpath']}  ->  {p['target_rel']}{fmnote}")
    for relpath, target_rel, why in plan_skip:
        print(f"  SKIP    {relpath}  ->  {target_rel}  ({why})")
    for relpath, why in plan_review:
        print(f"  REVIEW  {relpath}  —  {why}（不自动搬，交人/intake 处理）")

    if dry:
        print(f"  → 计划: {len(plan_new)} new, {len(plan_skip)} skip, {len(plan_review)} review"
              f"（DRY-RUN，未动文件）。审核无误后加 --apply 执行。")
        return 0

    # ── --apply 执行 ──
    applied = 0
    for p in plan_new:
        os.makedirs(os.path.dirname(p["target_abs"]) or ".", exist_ok=True)
        text = read_text(p["src"])
        out, added = ensure_frontmatter(text, p["title"], a.date, a.ctype)
        if added:
            with open(p["target_abs"], "w", encoding="utf-8") as f:
                f.write(out)
        else:
            shutil.copyfile(p["src"], p["target_abs"])
        applied += 1
        print(f"  [OK] {p['relpath']} -> {p['target_rel']}" + ("  (+frontmatter)" if added else ""))

    print(f"  → 搬入 {applied} 个；跳过 {len(plan_skip)}；待审 {len(plan_review)}。")
    print(f"  下一步: 在 {a.zone}/ 各目录补/更新 zone README（Agent Packet + 文件级索引），"
          f"再跑 substrate-doctor，最后交集成提交。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
