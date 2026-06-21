#!/usr/bin/env python3
"""0002-todo-zone — 把根 TODO.md 升级成 todo/ zone（零依赖，python3 标准库）。

v0.3.0 起：待办从「实例根单文件 `TODO.md`」升级为 **`todo/` zone**——支持给主人一个 + 每个
agent 各一个 todo 文件（per-agent 由 `fleet/` 派生，由 `substrate-todo` 维护），统一放 `todo/`
文件夹并带文件级索引。本迁移做这些（幂等、可回滚=git reset）：
  1. 把现有 root `TODO.md` 的内容搬进 `todo/owner.md`（补最小 frontmatter：title/created/updated/type）；
  2. 建 `todo/README.md`（zone 索引：Agent Packet + 文件级索引块，登记 owner.md）；
  3. 在 `governance/zones.md` 的 YAML 块注册 `todo` zone；
  4. 删除 root `TODO.md`（内容已无损搬入 owner.md）。

用法:
  python3 apply.py <INSTANCE_ROOT>            # dry-run：只打算做什么
  python3 apply.py <INSTANCE_ROOT> --apply    # 执行
  python3 apply.py <INSTANCE_ROOT> --check    # verify：是否已达 v0.3.0 todo zone 形态

退出码: 0=成功/已达标; 1=check 未达标; 2=调用错误。

约束: 只对传入实例路径操作；纯标准库；幂等（已迁移则各步跳过）；日期用占位符（不取 wall-clock，保证可复现）。
"""
import sys, os, re

DATE = "YYYY-MM-DD"   # 占位（不取 wall-clock；集成者/curator 后填）。doctor 只校验键在场。
IDX_START = "<!-- INDEX:START（substrate 自动维护：块内每次 reindex 会被重写，块外内容保留）-->"
IDX_END = "<!-- INDEX:END -->"

TODO_ZONE_ENTRY = (
    "  - id: todo\n"
    "    path: todo/\n"
    "    purpose: 待办清单（主人一个 owner.md + 每个 agent 一个，per-agent 由 fleet 派生）\n"
    "    schema: todo-zone-v1\n"
    "    maintainer_skill: substrate-todo\n"
    "    readers: [all]\n"
    "    writers: [all]\n"
    "    disposition: canonical\n"
    "    privacy: private\n"
)

OWNER_HEADER = (
    "---\n"
    "title: 待办 — 主人（owner）\n"
    f"created: {DATE}\n"
    f"updated: {DATE}\n"
    "type: todo\n"
    "---\n\n"
)

README_BODY = (
    "# todo — 待办 zone\n\n"
    "> **Agent Packet**\n"
    "> - zone: todo\n"
    "> - 维护 skill: `substrate-todo`\n"
    "> - canonical: 本目录下每个 `*.md` = 一份待办清单（`owner.md` 给主人；`<agent>.md` 给各 agent，按 `fleet/` 派生）\n"
    "> - 写前查: 对应那份清单里是否已有该条（去重）\n"
    "> - 写后更新: 改对应清单；新增/删清单文件时刷新下方索引（`substrate-curator reindex --dir todo`）\n"
    "> - doctor 检查: frontmatter 合规；索引登记；互链<2 仅提醒（待办本就少链接）\n\n"
    "每份待办固定三小节：**进行中 / 待办 / 已完成**。一条一行、动词开头；展不开的细节放对应知识/项目页只留链接。\n\n"
    f"{IDX_START}\n\n"
    "| 文件 | 摘要 |\n"
    "|------|------|\n"
    "| [[owner]] | 待办 — 主人（owner） |\n\n"
    f"{IDX_END}\n"
)


def read_text(p):
    try:
        return open(p, encoding="utf-8-sig", errors="replace").read()
    except Exception:
        return None


def state(root):
    """返回当前形态布尔：(owner_exists, zone_registered, root_todo_exists)。"""
    owner = os.path.isfile(os.path.join(root, "todo", "owner.md"))
    zt = read_text(os.path.join(root, "governance", "zones.md")) or ""
    m = re.search(r"```yaml\n(.*?)```", zt, re.S)
    block = m.group(1) if m else zt
    zone = re.search(r"(?m)^\s*-\s+id:\s*todo\b", block) is not None
    roottodo = os.path.isfile(os.path.join(root, "TODO.md"))
    return owner, zone, roottodo


def do_apply(root):
    actions = []
    tdir = os.path.join(root, "todo")
    owner_p = os.path.join(tdir, "owner.md")
    root_todo = os.path.join(root, "TODO.md")

    # 1) owner.md（搬 root TODO.md 内容；幂等：已存在则不动）
    if not os.path.isfile(owner_p):
        os.makedirs(tdir, exist_ok=True)
        body = ""
        if os.path.isfile(root_todo):
            raw = read_text(root_todo) or ""
            # 剥掉原 TODO.md 顶部的 H1 标题（owner.md 用 frontmatter 的 title），其余正文逐字保留
            body = re.sub(r"\A\s*#\s+.*\n", "", raw)
        with open(owner_p, "w", encoding="utf-8") as f:
            f.write(OWNER_HEADER + body.lstrip("\n"))
        actions.append("建 todo/owner.md（搬入 root TODO.md 内容 + frontmatter）")

    # 2) todo/README.md（索引）
    readme_p = os.path.join(tdir, "README.md")
    if not os.path.isfile(readme_p):
        os.makedirs(tdir, exist_ok=True)
        with open(readme_p, "w", encoding="utf-8") as f:
            f.write(README_BODY)
        actions.append("建 todo/README.md（Agent Packet + 索引）")

    # 3) 注册 todo zone（幂等）
    zones_p = os.path.join(root, "governance", "zones.md")
    zt = read_text(zones_p)
    if zt is not None and not re.search(r"(?m)^\s*-\s+id:\s*todo\b", zt):
        # 插在 ```yaml\nzones:\n 之后（顺序无关）
        nt, n = re.subn(r"(```yaml\n[ \t]*zones:[ \t]*\n)", r"\1" + TODO_ZONE_ENTRY, zt, count=1)
        if n == 1:
            with open(zones_p, "w", encoding="utf-8") as f:
                f.write(nt)
            actions.append("在 governance/zones.md 注册 todo zone")

    # 4) 删 root TODO.md（内容已搬入 owner.md）
    if os.path.isfile(root_todo) and os.path.isfile(owner_p):
        os.remove(root_todo)
        actions.append("删除 root TODO.md（内容已无损搬入 todo/owner.md）")

    return actions


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    flags = {a for a in argv if a.startswith("--")}
    if not args:
        print("apply.py: 缺少 <INSTANCE_ROOT>"); return 2
    root = os.path.abspath(args[0])
    if not os.path.isdir(root):
        print(f"apply.py: 不是目录: {root}"); return 2

    if "--check" in flags:
        owner, zone, _ = state(root)
        if owner and zone:
            print("0002 verify: OK — todo/owner.md 在 + todo zone 已注册"); return 0
        miss = []
        if not owner: miss.append("缺 todo/owner.md")
        if not zone: miss.append("zones.md 未注册 todo")
        print(f"0002 verify: 未达标（{', '.join(miss)}）"); return 1

    owner, zone, roottodo = state(root)
    mode = "APPLY" if "--apply" in flags else "DRY-RUN"
    print(f"0002-todo-zone  root={root}  mode={mode}")
    if owner and zone and not roottodo:
        print("  已是 v0.3.0 todo zone 形态，无需改动（幂等）"); return 0

    if "--apply" not in flags:
        plan = []
        if not owner: plan.append("建 todo/owner.md（搬 root TODO.md）")
        if not os.path.isfile(os.path.join(root, "todo", "README.md")): plan.append("建 todo/README.md")
        if not zone: plan.append("注册 todo zone")
        if roottodo: plan.append("删 root TODO.md")
        for p in plan: print(f"  计划: {p}")
        print("  → dry-run，未改动。加 --apply 执行。")
        return 0

    actions = do_apply(root)
    for a in actions:
        print(f"  ✓ {a}")
    if not actions:
        print("  （无改动）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
