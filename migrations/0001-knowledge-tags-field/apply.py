#!/usr/bin/env python3
"""0001-knowledge-tags-field — 给缺 tags 字段的知识页补 tags:[]（零依赖，python3 标准库）。

【示例迁移的变换脚本，供 fork 者参考】幂等、CWD 无关、默认 dry-run。

用法:
  python3 apply.py <INSTANCE_ROOT>            # dry-run：只打算改哪些页，不写盘
  python3 apply.py <INSTANCE_ROOT> --apply    # 真正写盘（追加 tags: [] 到缺字段的页）
  python3 apply.py <INSTANCE_ROOT> --check    # verify：检查是否全部已补齐（不改盘）

退出码:
  0 = 成功（dry-run 列出计划 / apply 写完 / check 全部已补齐）
  1 = check 模式下仍有页缺 tags（verify 失败）
  2 = 调用错误（路径不对等）

约束:
  - 只对传入的【实例路径】操作；只追加 frontmatter 里的 `tags: []`，不碰正文与其它字段。
  - 幂等：已有 tags 的页跳过；重复跑结果一致。
  - frontmatter 用受限子集正则解析（不假设 PyYAML）。
  - 豁免结构页（README / governance/* / _前缀 / by-* 分片），与 doctor 一致。
"""
import sys, os, re, glob


def rel(root, p):
    return os.path.relpath(p, root).replace(os.sep, "/")


def is_structural(root, p):
    r = rel(root, p)
    if os.path.basename(p) == "README.md":
        return True
    if r == "governance" or r.startswith("governance/"):
        return True
    if os.path.basename(p).startswith("_"):
        return True
    if any(seg.startswith("by-") for seg in r.split("/")[:-1]):
        return True
    return False


def read_text(p):
    try:
        return open(p, encoding="utf-8-sig", errors="replace").read()
    except Exception:
        return None


def split_frontmatter(text):
    """返回 (fm_body, start_idx, end_idx)，定位 frontmatter 块；无则 (None, None, None)。

    start_idx/end_idx 是 fm_body（两个 --- 之间内容）在原文中的字符区间。
    """
    m = re.match(r"(\s*---[ \t]*\r?\n)(.*?)(\r?\n---[ \t]*(?:\r?\n|$))", text, re.S)
    if not m:
        return None, None, None
    return m.group(2), m.start(2), m.end(2)


def has_tags(fm_body):
    # 顶层 tags 键在第 0 列；缩进的 tags（嵌套键）不算（与 doctor 列 0 解析一致）。
    return re.search(r"(?m)^tags[ \t]*:", fm_body) is not None


def target_pages(root):
    """knowledge/ 下的非结构内容页。"""
    out = []
    kdir = os.path.join(root, "knowledge")
    if not os.path.isdir(kdir):
        return out
    for p in sorted(glob.glob(kdir + "/**/*.md", recursive=True)):
        if is_structural(root, p):
            continue
        out.append(p)
    return out


def needs_migration(root, page):
    """该页是否缺 tags（None 表示无 frontmatter，按缺处理但单独标记）。"""
    text = read_text(page)
    if text is None:
        return None  # 读不了，交给 doctor 报告，不在这里补
    fm, _, _ = split_frontmatter(text)
    if fm is None:
        return "no-frontmatter"
    return "missing" if not has_tags(fm) else None


def apply_to_page(page):
    """在 frontmatter 块末尾追加 `tags: []`；逐字保留原 BOM 与换行风格（纯追加，不改正文/其它字段）。"""
    try:
        with open(page, "rb") as f:
            raw = f.read()
    except Exception:
        return False
    bom = raw.startswith(b"\xef\xbb\xbf")
    try:
        text = raw[3:].decode("utf-8") if bom else raw.decode("utf-8")
    except UnicodeDecodeError:
        return False   # 非 UTF-8：本迁移不处理，交 doctor 报告
    fm, start, end = split_frontmatter(text)
    if fm is None or has_tags(fm):
        return False
    nl = "\r\n" if "\r\n" in text else "\n"
    new_fm = fm.rstrip("\r\n") + nl + "tags: []"
    new_text = text[:start] + new_fm + text[end:]
    out = (b"\xef\xbb\xbf" if bom else b"") + new_text.encode("utf-8")
    with open(page, "wb") as f:
        f.write(out)
    return True


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    flags = {a for a in argv if a.startswith("--")}
    if not args:
        print("apply.py: 缺少 <INSTANCE_ROOT> 参数")
        return 2
    root = os.path.abspath(args[0])
    if not os.path.isdir(root):
        print(f"apply.py: 不是目录: {root}")
        return 2

    check = "--check" in flags
    apply = "--apply" in flags

    pages = target_pages(root)

    if check:
        # verify 范围须与 apply 一致：只看「有 frontmatter 却缺 tags」的页。
        # 无 frontmatter 的页本迁移不处理（doctor 会单独报 frontmatter 缺失），不算 verify 失败。
        bad = [rel(root, p) for p in pages if needs_migration(root, p) == "missing"]
        if bad:
            print(f"0001 verify: 仍有 {len(bad)} 页有 frontmatter 却缺 tags:")
            for r in bad:
                print(f"  [MISSING] {r}")
            return 1
        print(f"0001 verify: OK — knowledge/ 下有 frontmatter 的页都含 tags")
        return 0

    plan = [(p, needs_migration(root, p)) for p in pages]
    todo = [(p, s) for p, s in plan if s == "missing"]
    skip_nofm = [p for p, s in plan if s == "no-frontmatter"]

    mode = "APPLY" if apply else "DRY-RUN"
    print(f"0001-knowledge-tags-field  root={root}  mode={mode}")
    for p, _ in todo:
        print(f"  补 tags:[]   {rel(root, p)}")
    for p in skip_nofm:
        print(f"  跳过(无frontmatter，交 doctor 报告)  {rel(root, p)}")
    if not todo and not skip_nofm:
        print("  无需改动（所有 knowledge 页都已有 tags）")

    if not apply:
        print(f"  → 计划补 {len(todo)} 页（dry-run，未写盘）")
        return 0

    changed = 0
    for p, _ in todo:
        if apply_to_page(p):
            changed += 1
    print(f"  → 已补 {changed} 页 tags:[]")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
