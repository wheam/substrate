#!/usr/bin/env python3
"""substrate-doctor — 防退化体检 + 迁移测试套件（零依赖，python3 标准库）。

用法:  python3 doctor.py [INSTANCE_ROOT]   (默认当前目录)
退出码: 0 = 无 error（可有 warning/advice）; 1 = 有 error; 2 = 调用错误（路径不对）。

设计约束（见引擎 docs/BUILD-PLAN.md §15 P1）:
  - 不假设 PyYAML：frontmatter / zones / registry 用受限子集正则解析。
  - 抽 [[wikilink]] 前先剥离 inline code 与 fenced code block。
  - 孤儿 / frontmatter 检查豁免 governance/* 与 README/索引/分片结构页。
  - 对真实数据要 robust：BOM / 非 UTF-8 / 空 CSV / 尾空行 / 重名 / prose 数字都不能误判或崩。
"""
import sys, os, re, glob, csv

REQUIRED_FRONTMATTER = ["title", "created", "updated", "type"]
errors, warnings, advice = [], [], []
def err(m):  errors.append(m)
def warn(m): warnings.append(m)
def adv(m):  advice.append(m)

def read_text(p):
    try:
        return open(p, encoding="utf-8-sig", errors="replace").read()
    except Exception:
        return None

def strip_code(t):
    t = re.sub(r"```.*?```", "", t, flags=re.S)   # fenced blocks
    t = re.sub(r"`[^`]*`", "", t)                 # inline code
    return t

def rel(root, p): return os.path.relpath(p, root)

def is_structural(root, p):
    r = rel(root, p).replace(os.sep, "/")
    if os.path.basename(p) == "README.md": return True
    if r == "governance" or r.startswith("governance/"): return True
    if os.path.basename(p).startswith("_"): return True
    if any(seg.startswith("by-") for seg in r.split("/")[:-1]): return True
    return False

def wikilink_targets(text):
    """返回 [(raw_target, name)]，已剥 code、去 alias/#anchor。"""
    out = []
    for raw in re.findall(r"\[\[([^\]]+)\]\]", strip_code(text)):
        tgt = raw.split("|")[0].split("#")[0].strip()
        if tgt: out.append(tgt)
    return out

def frontmatter_keys(text):
    m = re.match(r"\s*---\s*\n(.*?)\n---", text, re.S)   # 容忍前导空白/BOM(读时已去)
    if not m: return None
    return set(re.findall(r"(?m)^([A-Za-z_][\w-]*):", m.group(1)))

def csv_rows(path):
    try:
        with open(path, newline="", encoding="utf-8-sig", errors="replace") as f:
            rows = [r for r in csv.reader(f) if any(c.strip() for c in r)]
        return max(len(rows) - 1, 0)   # 减表头；空文件→0
    except Exception:
        return 0

def main(root):
    root = os.path.abspath(root)
    if not os.path.isdir(root):
        print(f"doctor: 不是目录: {root}"); return 2
    mds = sorted(glob.glob(root + "/**/*.md", recursive=True))
    allfiles = set(mds)
    texts = {}
    for m in mds:
        t = read_text(m)
        if t is None:
            err(f"无法读取（非 UTF-8/损坏）  {rel(root,m)}"); t = ""
        texts[m] = t
    base = {}
    for m in mds:
        base.setdefault(os.path.splitext(os.path.basename(m))[0], []).append(m)

    def resolve(tgt):
        """返回命中文件列表；优先按相对路径，再按 basename。"""
        if "/" in tgt:
            cand = os.path.normpath(os.path.join(root, tgt if tgt.endswith(".md") else tgt + ".md"))
            if cand in allfiles: return [cand]
        return base.get(re.sub(r"\.md$", "", os.path.basename(tgt)), [])

    # 1) 断链 + 入链统计（剥 code；排除自链；重名告警）
    inbound = {m: 0 for m in mds}
    for m in mds:
        for tgt in wikilink_targets(texts[m]):
            hits = resolve(tgt)
            if not hits:
                err(f"断链  {rel(root,m)} -> [[{tgt}]]")
            else:
                if len(hits) > 1:
                    warn(f"重名链接  {rel(root,m)} -> [[{tgt}]] 命中 {len(hits)} 个同名文件（孤儿/断链检测会失真）")
                for x in hits:
                    if x != m: inbound[x] += 1   # 自链不算入链

    # 2) 孤儿（内容页无入链）
    for m in mds:
        if is_structural(root, m): continue
        if inbound[m] == 0:
            err(f"孤儿  {rel(root,m)}（无任何入链 wikilink）")

    # 3) frontmatter 合规（内容页）
    for m in mds:
        if is_structural(root, m): continue
        keys = frontmatter_keys(texts[m])
        if keys is None:
            err(f"frontmatter 缺失  {rel(root,m)}")
        else:
            miss = [k for k in REQUIRED_FRONTMATTER if k not in keys]
            if miss: err(f"frontmatter 缺字段  {rel(root,m)}: {', '.join(miss)}")

    # 4) 索引漂移（同目录有 README.md 时，内容兄弟页须以整词/链接登记在该 README）
    def registered(readme_text):
        names = {re.sub(r"\.md$", "", os.path.basename(t)) for t in wikilink_targets(readme_text)}
        names |= {re.sub(r"\.md$", "", os.path.basename(p)) for p in re.findall(r"[\w./-]+\.md", readme_text)}
        return names
    for m in mds:
        if is_structural(root, m): continue
        readme = os.path.join(os.path.dirname(m), "README.md")
        if os.path.exists(readme):
            bn = os.path.splitext(os.path.basename(m))[0]
            if bn not in registered(texts.get(readme) or read_text(readme) or ""):
                err(f"索引漂移  {rel(root,m)} 未登记在 {rel(root,readme)}")

    # 5) 收藏计数漂移（递归找 data.csv；只认页面里**粗体**声明的计数，避免 prose 误报）
    for csvf in glob.glob(root + "/collections/**/data.csv", recursive=True):
        n = csv_rows(csvf)
        cdir = os.path.dirname(csvf)
        for page in glob.glob(cdir + "/**/*.md", recursive=True):
            for claimed in re.findall(r"\*\*\s*(\d+)\s*\*\*\s*(?:条|rows|entries)", texts.get(page) or read_text(page) or ""):
                if int(claimed) != n:
                    err(f"计数漂移  {rel(root,page)} 声称 {claimed}，但 {rel(root,csvf)} 有 {n} 行")

    # 6) registry pin（缺 pin = ERROR，对齐 SKILL.md 与 registry.schema）
    reg = os.path.join(root, "skills", "_registry.md")
    if os.path.isfile(reg):
        m = re.search(r"```yaml\n(.*?)```", read_text(reg) or "", re.S)
        block = "\n".join(l for l in (m.group(1) if m else "").splitlines() if not l.lstrip().startswith("#"))
        for chunk in re.split(r"(?m)^\s*-\s+name:", block)[1:]:
            name = chunk.splitlines()[0].strip()
            if "upstream_git_url" in chunk and not re.search(r"(?m)^\s*pin:\s*\S", chunk):
                err(f"registry 缺 pin（裸追上游有供应链风险）: {rel(root,reg)} 条目 {name}")

    # 7) 毕业阈值（advisory，按 zone 条目解析，id 与阈值同源）
    zones = os.path.join(root, "governance", "zones.md")
    if os.path.isfile(zones):
        m = re.search(r"```yaml\n(.*?)```", read_text(zones) or "", re.S)
        for chunk in re.split(r"(?m)^\s*-\s+id:", (m.group(1) if m else ""))[1:]:
            zid = chunk.splitlines()[0].strip()
            gm = re.search(r"graduation:.*?rows>(\d+)", chunk)
            if not gm: continue
            thr = int(gm.group(1))
            pm = re.search(r"(?m)^\s*path:\s*(\S+)", chunk)
            zpath = (pm.group(1).rstrip("/") if pm else zid)
            for csvf in glob.glob(os.path.join(root, zpath, "**", "data.csv"), recursive=True):
                n = csv_rows(csvf)
                if n > thr:
                    adv(f"毕业建议  {rel(root,csvf)} 有 {n} 行 > 阈值 {thr}（zone {zid}）：考虑分片/迁移")

    print(f"substrate-doctor: {os.path.basename(root)}  ({len(mds)} md 文件)")
    for tag, items in (("ERROR", errors), ("WARN", warnings), ("ADVICE", advice)):
        for it in items: print(f"  [{tag}] {it}")
    print(f"  → {len(errors)} error, {len(warnings)} warn, {len(advice)} advice")
    return 1 if errors else 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "."))
