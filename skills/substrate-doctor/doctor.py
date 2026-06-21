#!/usr/bin/env python3
"""substrate-doctor — 防退化体检 + 迁移测试套件（零依赖，python3 标准库）。

用法:  python3 doctor.py [INSTANCE_ROOT]   (默认当前目录)
退出码: 0 = 无 error（可有 warning/advice）; 1 = 有 error; 2 = 调用错误（路径不对）。

设计约束（见引擎 docs/BUILD-PLAN.md §15 P1）:
  - 不假设 PyYAML：frontmatter / zones / registry 用受限子集正则解析。
  - 抽 [[wikilink]] 前先剥离 inline code 与 fenced code block。
  - 孤儿 / frontmatter 检查豁免 governance/* 与 README/索引/分片结构页，
    以及 skills/*（其顶部是 skill-manifest，不是内容页；skill 里的 [[..]] 是示例，不计入内容图）。
  - 对真实数据要 robust：BOM / 非 UTF-8 / 空 CSV / 尾空行 / 重名 / prose 数字都不能误判或崩。
"""
import sys, os, re, glob, csv

REQUIRED_FRONTMATTER = ["title", "created", "updated", "type"]
MANIFEST_REQUIRED = ["name", "target_runtimes", "risk_level"]   # 见 schemas/skill-manifest.schema.yaml
errors, warnings, advice = [], [], []
def err(m):  errors.append(m)
def warn(m): warnings.append(m)
def adv(m):  advice.append(m)

def read_text(p):
    try:
        return open(p, encoding="utf-8-sig", errors="replace").read()
    except Exception:
        return None

def strip_indented_code(t):
    """剥 CommonMark 缩进式代码块：以 ≥4 空格或 tab 缩进、且【前有空行或在文首】的连续行块
    （缩进代码块不能打断段落，故必有前导空行；块内允许夹空行）。这样代码示例里的
    [[wikilink]] 不会被误判断链。**保守**：只剥前有空行的缩进块，浅缩进（<4）列表续行或
    无前导空行的缩进行一律保留——宁可漏剥也绝不把真实链接吞掉（避免漏报真断链）。"""
    lines = t.split("\n")
    out, prev_blank, i, n = [], True, 0, len(lines)
    ind = lambda s: s.startswith("    ") or s.startswith("\t")
    while i < n:
        if prev_blank and ind(lines[i]) and lines[i].strip():
            while i < n and ((ind(lines[i]) and lines[i].strip())
                             or (lines[i].strip() == "" and i + 1 < n and ind(lines[i + 1]) and lines[i + 1].strip())):
                i += 1                            # 吃掉缩进代码块整块（含块内空行），不计入输出
            prev_blank = False
            continue
        out.append(lines[i])
        prev_blank = (lines[i].strip() == "")
        i += 1
    return "\n".join(out)

def strip_code(t):
    t = re.sub(r"```.*?```", "", t, flags=re.S)   # fenced blocks (backtick)
    t = re.sub(r"~~~.*?~~~", "", t, flags=re.S)   # fenced blocks (tilde)
    t = strip_indented_code(t)                    # CommonMark 缩进式代码块（≥4 空格/tab，前有空行）
    t = re.sub(r"`[^`]*`", "", t)                 # inline code
    return t

def rel(root, p): return os.path.relpath(p, root)

def under(root, p, top):
    """p 是否在 root 下的 top/ 子树里（或就是 top）。"""
    r = rel(root, p).replace(os.sep, "/")
    return r == top or r.startswith(top + "/")

def is_structural(root, p):
    r = rel(root, p).replace(os.sep, "/")
    if os.path.basename(p) == "README.md": return True
    if r == "TODO.md": return True   # 实例根的待办 checklist：无 frontmatter/入链，是结构页（由 substrate-todo 维护）
    if under(root, p, "governance"): return True
    if under(root, p, "skills"): return True   # skill 目录顶部是 manifest，不是内容页（单独 lint，见检查 8）
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
        try:
            raw = open(m, "rb").read()
        except Exception:
            err(f"无法读取  {rel(root,m)}"); texts[m] = ""; continue
        try:
            texts[m] = raw.decode("utf-8-sig")          # 严格解码：能发现真正的非 UTF-8
        except UnicodeDecodeError:
            warn(f"非 UTF-8 编码（按替换字符解析，可能有乱码）  {rel(root,m)}")
            texts[m] = raw.decode("utf-8-sig", errors="replace")
    base = {}
    for m in mds:
        base.setdefault(os.path.splitext(os.path.basename(m))[0], []).append(m)

    def resolve(tgt):
        """返回命中文件列表。路径式（含 /）必须按路径解析，不退回 basename
        （否则写错路径的链接会被 basename 兜底成功而漏判断链）。"""
        if "/" in tgt:
            cand = os.path.normpath(os.path.join(root, tgt if tgt.endswith(".md") else tgt + ".md"))
            return [cand] if cand in allfiles else []
        return base.get(re.sub(r"\.md$", "", os.path.basename(tgt)), [])

    # 1) 断链 + 入链统计（剥 code；排除自链；重名告警）。
    #    skills/ 里的 [[..]] 是示例/说明，不计入内容图：既不报断链，也不算入链。
    inbound = {m: 0 for m in mds}
    for m in mds:
        if under(root, m, "skills"):
            continue
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

    # 2b) 互链 ≥2（宪法【建议】：每页宜链到 2 个相关页；剥 code、排除自链；豁免结构页与 skills/）
    #     注：这是【提醒不报错】（WARN，不影响退出码）——保持知识图连通是好习惯，但不强制、不拦路。
    #     删页/加页时不应因此被卡（见 substrate-curator 的 rm：删页会自动清反向链接）。
    for m in mds:
        if is_structural(root, m) or under(root, m, "skills"): continue
        self_stem = os.path.splitext(os.path.basename(m))[0]
        outs = {re.sub(r"\.md$", "", os.path.basename(t)) for t in wikilink_targets(texts[m])}
        outs.discard(self_stem)
        if len(outs) < 2:
            warn(f"互链不足  {rel(root,m)} 只链到 {len(outs)} 个页（建议每页 ≥2 个 [[wikilink]]，仅提醒不报错）")

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
        # 整词匹配 .md 路径：尾随 lookahead 排除 page.md.bak 这类子串误判为已登记
        names |= {re.sub(r"\.md$", "", os.path.basename(p))
                  for p in re.findall(r"[\w./-]+\.md(?![\w.])", readme_text)}
        return names
    for m in mds:
        if is_structural(root, m): continue
        readme = os.path.join(os.path.dirname(m), "README.md")
        if os.path.exists(readme):
            bn = os.path.splitext(os.path.basename(m))[0]
            if bn not in registered(texts.get(readme) or read_text(readme) or ""):
                err(f"索引漂移  {rel(root,m)} 未登记在 {rel(root,readme)}")

    # 5) 收藏计数漂移（递归找 data.csv；只校验与 data.csv **同目录**的索引页粗体计数 == 主表行数。
    #    分类分片在 by-*/ 子目录里，天然是子集，不与主表总数比——避免对多类别分片误报。）
    for csvf in glob.glob(root + "/collections/**/data.csv", recursive=True):
        n = csv_rows(csvf)
        cdir = os.path.dirname(csvf)
        for page in glob.glob(cdir + "/*.md"):
            for claimed in re.findall(r"\*\*\s*(\d+)\s*\*\*\s*(?:条|rows|entries)", texts.get(page) or read_text(page) or ""):
                if int(claimed) != n:
                    err(f"计数漂移  {rel(root,page)} 声称 {claimed}，但 {rel(root,csvf)} 有 {n} 行")

    # 5b) zones 契约校验（schema 必填字段在场 + id 唯一 + path 存在）——doctor 解析治理契约，不空过。
    zones_f = os.path.join(root, "governance", "zones.md")
    if os.path.isfile(zones_f):
        zt = read_text(zones_f) or ""
        ym = re.search(r"```yaml\n(.*?)```", zt, re.S)
        zblock = ym.group(1) if ym else ""
        seen_ids = set()
        for chunk in re.split(r"(?m)^\s*-\s+id:", zblock)[1:]:
            zid = chunk.splitlines()[0].strip().strip("'\"")
            present = set(re.findall(r"(?m)^\s*([A-Za-z_][\w-]*)\s*:", chunk)) | {"id"}
            if not zid:
                err(f"zones 契约: 有 zone 条目缺 id 值  ({rel(root,zones_f)})"); continue
            if zid in seen_ids:
                err(f"zones 契约: zone id 重复  {zid}  ({rel(root,zones_f)})")
            seen_ids.add(zid)
            miss = [k for k in ("path", "schema", "maintainer_skill", "readers", "writers") if k not in present]
            if miss:
                err(f"zones 契约: zone '{zid}' 缺必填字段 {', '.join(miss)}  ({rel(root,zones_f)})")
            pm = re.search(r"(?m)^\s*path:\s*(\S+)", chunk)
            if pm and not os.path.isdir(os.path.join(root, pm.group(1).strip("'\"").rstrip("/"))):
                warn(f"zones 契约: zone '{zid}' 的 path '{pm.group(1)}' 在实例里不存在  ({rel(root,zones_f)})")

    # 6) registry pin（缺 pin = ERROR；pin 是 main/master/HEAD 这类移动 ref 却未声明 trusted_floating=ERROR→WARN）
    reg = os.path.join(root, "skills", "_registry.md")
    if os.path.isfile(reg):
        m = re.search(r"```yaml\n(.*?)```", read_text(reg) or "", re.S)
        block = "\n".join(l for l in (m.group(1) if m else "").splitlines() if not l.lstrip().startswith("#"))
        for chunk in re.split(r"(?m)^\s*-\s+name:", block)[1:]:
            name = chunk.splitlines()[0].strip()
            kindm = re.search(r"(?m)^\s*kind:\s*(\S+)", chunk)
            kind = (kindm.group(1).strip("'\"") if kindm else "git")
            if kind == "plugin":
                # 插件机制管理：不 clone、无 pin。只要求登记了 source。
                if not re.search(r"(?m)^\s*source:\s*\S", chunk):
                    err(f"registry kind=plugin 缺 source（无法标识插件来源）: {rel(root,reg)} 条目 {name}")
                continue
            if "upstream_git_url" not in chunk:
                continue
            pinm = re.search(r"(?m)^\s*pin:\s*(\S+)", chunk)
            if not pinm:
                err(f"registry 缺 pin（裸追上游有供应链风险）: {rel(root,reg)} 条目 {name}")
            elif pinm.group(1).strip("'\"").lower() in ("main", "master", "head") \
                    and not re.search(r"(?m)^\s*trusted_floating:\s*true", chunk):
                warn(f"registry pin 追踪移动 ref（{pinm.group(1)}）却未声明 trusted_floating: true: {rel(root,reg)} 条目 {name}")

    # 7) 毕业阈值（advisory，按 zone 条目解析，id 与阈值同源；容忍 rows>N / rows > N）
    zones = os.path.join(root, "governance", "zones.md")
    if os.path.isfile(zones):
        m = re.search(r"```yaml\n(.*?)```", read_text(zones) or "", re.S)
        for chunk in re.split(r"(?m)^\s*-\s+id:", (m.group(1) if m else ""))[1:]:
            zid = chunk.splitlines()[0].strip()
            gm = re.search(r"graduation:.*?rows\s*>\s*(\d+)", chunk)
            if not gm: continue
            thr = int(gm.group(1))
            pm = re.search(r"(?m)^\s*path:\s*(\S+)", chunk)
            zpath = (pm.group(1).rstrip("/") if pm else zid)
            for csvf in glob.glob(os.path.join(root, zpath, "**", "data.csv"), recursive=True):
                n = csv_rows(csvf)
                if n > thr:
                    adv(f"毕业建议  {rel(root,csvf)} 有 {n} 行 > 阈值 {thr}（zone {zid}）：考虑分片/迁移")

    # 8) skills/ 清单 lint（WARN）：committed own-skill 的 SKILL.md 应是合规 manifest（见 skill-manifest.schema）。
    #    只 lint 一层 skills/<name>/SKILL.md；_前缀目录（_incoming 等）由 substrate-intake 守门，不在此 lint。
    for sk in sorted(glob.glob(root + "/skills/*/SKILL.md")):
        if os.path.basename(os.path.dirname(sk)).startswith("_"):
            continue
        keys = frontmatter_keys(texts.get(sk) or read_text(sk) or "")
        if keys is None:
            warn(f"skill 缺 manifest frontmatter  {rel(root,sk)}（见 skill-manifest.schema）")
        else:
            miss = [k for k in MANIFEST_REQUIRED if k not in keys]
            if miss: warn(f"skill manifest 缺字段  {rel(root,sk)}: {', '.join(miss)}")

    print(f"substrate-doctor: {os.path.basename(root)}  ({len(mds)} md 文件)")
    for tag, items in (("ERROR", errors), ("WARN", warnings), ("ADVICE", advice)):
        for it in items: print(f"  [{tag}] {it}")
    print(f"  → {len(errors)} error, {len(warnings)} warn, {len(advice)} advice")
    return 1 if errors else 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "."))
