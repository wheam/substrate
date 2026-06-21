#!/usr/bin/env python3
"""substrate-sync — 按 runtime 选择性安装 skill + 写本地清单（零依赖）。

用法:
  python3 sync.py --src <skills目录> [--target <skill 目录>] \
                  --runtime claude-code [--registry <_registry.md>] [--apply]

默认 **dry-run**（只打计划，不动文件）；加 --apply 才真正拷贝/clone。
--target 省略时：从 adapters/<runtime>/adapter.yaml 推断安装目录（view-layer 的 adapter 会被拒绝）。
本地清单（installed-skills.json）写到 --target，**不入库**。

选择性安装（fail-closed）：
  - 只装 `target_runtimes` 含本 runtime 或 `all` 的 skill；**未声明 target_runtimes 的一律跳过**
    （不再 fail-open 装到所有 runtime）。要全 runtime 请显式写 `target_runtimes: [all]`。
  - registry（第三方）：缺 pin 拒绝 clone；pin 检出失败即视为安装失败，**绝不静默停在默认分支**；
    安装成功后删除 .git，冻结为该 commit 的快照（杜绝 stray `git pull` 漂移），并把 commit 记入清单。

退出码: 0 = 全部成功; 1 = 有 registry 安装失败/跳过; 2 = 调用错误。
"""
import sys, os, re, json, shutil, argparse, subprocess

# skill 名必须是单段安全标识符；防 registry 写 `name: ../victim` 这类路径穿越（删/写 target 外目录）。
SKILL_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

def safe_name(name):
    return bool(name) and name not in (".", "..") and SKILL_NAME_RE.match(name) is not None

def within_target(target, dest):
    """dest 必须落在 target 子树内（realpath 防符号链接绕过）——破坏性操作前的兜底。"""
    rt = os.path.realpath(target)
    rd = os.path.realpath(dest)
    return rd == rt or rd.startswith(rt + os.sep)

def field(text, key):
    """读列表字段。容忍 key 行前导缩进（registry 条目里 key 是缩进在 `- name:` 下的）。"""
    m = re.search(rf"(?m)^[ \t]*{key}:[ \t]*\[(.*?)\]", text)
    if m: return [x.strip().strip("'\"") for x in m.group(1).split(",") if x.strip()]
    m = re.search(rf"(?m)^[ \t]*{key}:[ \t]*\n((?:[ \t]*-[ \t]*.+\n?)+)", text)
    if m: return [re.sub(r"^[ \t]*-[ \t]*", "", l).strip().strip("'\"") for l in m.group(1).splitlines() if l.strip()]
    return []

def manifest_of(skill_dir):
    sk = os.path.join(skill_dir, "SKILL.md")
    if not os.path.isfile(sk): return None
    t = open(sk, encoding="utf-8-sig", errors="replace").read()
    return {"target_runtimes": field(t, "target_runtimes") if t.lstrip().startswith("---") else []}

def selected(runtimes, runtime):
    """fail-closed：未声明 target_runtimes（[]）不算选中。要全 runtime 显式写 [all]。"""
    return ("all" in runtimes) or (runtime in runtimes)

def parse_registry(path, runtime):
    """返回 (entries, undeclared, rejected)。entries=选中本 runtime 的；undeclared=未声明 target_runtimes 的；rejected=skill 名非法（路径穿越防护）的。"""
    if not path or not os.path.isfile(path): return [], [], []
    t = open(path, encoding="utf-8-sig", errors="replace").read()
    m = re.search(r"```yaml\n(.*?)```", t, re.S)
    block = "\n".join(l for l in (m.group(1) if m else "").splitlines() if not l.lstrip().startswith("#"))
    out, undeclared, rejected = [], [], []
    for chunk in re.split(r"(?m)^\s*-\s+name:", block)[1:]:
        name = chunk.splitlines()[0].strip().strip("'\"")
        url = (re.search(r"(?m)^\s*upstream_git_url:\s*(\S+)", chunk) or [None, None])[1]
        pinm = re.search(r"(?m)^\s*pin:\s*(\S+)", chunk)
        rts = field(chunk, "target_runtimes")   # 整块解析，含缩进/多行列表形式
        if not url:
            continue
        if not safe_name(name):
            rejected.append(name); continue       # 防路径穿越：非法 skill 名直接拒绝
        if not rts:
            undeclared.append(name); continue    # fail-closed：未声明 target_runtimes 不装
        if selected(rts, runtime):
            out.append({"name": name, "url": url, "pin": pinm.group(1) if pinm else None})
    return out, undeclared, rejected

def adapter_target(adapters_dir, runtime):
    """从 adapters/<runtime>/adapter.yaml 推断 skill 安装目录。返回 (target|None, err|None)。"""
    af = os.path.join(adapters_dir, runtime, "adapter.yaml")
    if not os.path.isfile(af):
        return None, f"找不到 adapter {af}（请显式传 --target，或核对 --runtime/--adapters-dir）"
    t = open(af, encoding="utf-8-sig", errors="replace").read()
    def g(key):
        m = re.search(rf"(?m)^[ \t]*{re.escape(key)}[ \t]*:[ \t]*(.+?)[ \t]*$", t)
        return (m.group(1).split(" #")[0].strip().strip("\"'") or None) if m else None
    if g("kind") == "view-layer":
        return None, f"adapter '{runtime}' 是 view-layer（视图层），不装 skill——不要对它跑 sync"
    target = g("target")
    if not target:
        return None, f"adapter '{runtime}' 未声明 skill_install.target；请显式传 --target"
    ov = g("target_env_override")
    if ov and os.environ.get(ov):
        return os.path.expanduser(os.environ[ov]), None
    mv = re.search(r"\$\{(\w+)\}", target)
    if mv:
        val = os.environ.get(mv.group(1))
        if val:
            target = target.replace(mv.group(0), val)
        else:
            fb = g("target_fallback")
            if not fb:
                return None, (f"adapter '{runtime}' 的 target 含未设环境变量 ${{{mv.group(1)}}} 且无 fallback；"
                              "请设该变量或显式传 --target")
            target = fb
    return os.path.expanduser(target), None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=".")
    ap.add_argument("--target")            # 省略则从 adapters/<runtime>/adapter.yaml 推断
    ap.add_argument("--runtime", default="claude-code")
    ap.add_argument("--adapters-dir")      # 默认 = 引擎 adapters/（按本脚本位置推断）
    ap.add_argument("--registry")
    ap.add_argument("--manifest")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    if not os.path.isdir(a.src):
        print(f"substrate-sync: --src 不是目录: {a.src}"); return 2
    if not a.target:
        adir = a.adapters_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "adapters")
        a.target, err = adapter_target(adir, a.runtime)
        if err:
            print(f"substrate-sync: {err}"); return 2
        print(f"  (--target 未给：从 adapter 推断为 {a.target})")
    dry = not a.apply
    plan_own, plan_reg, skipped, undeclared = [], [], [], []

    for entry in sorted(os.listdir(a.src)):
        d = os.path.join(a.src, entry)
        man = manifest_of(d)
        if man is None: continue
        rts = man["target_runtimes"]
        if not rts:
            undeclared.append(entry)             # fail-closed：未声明 target_runtimes，不装
        elif selected(rts, a.runtime):
            variant = f"SKILL.{a.runtime}.md"
            plan_own.append({"name": entry, "variant": variant if os.path.isfile(os.path.join(d, variant)) else "SKILL.md", "src": d})
        else:
            skipped.append(entry)

    plan_reg, reg_undeclared, reg_rejected = parse_registry(a.registry, a.runtime)
    undeclared += [f"registry:{n}" for n in reg_undeclared]

    print(f"substrate-sync  runtime={a.runtime}  target={a.target}  mode={'DRY-RUN' if dry else 'APPLY'}")
    for p in plan_own: print(f"  own      install {p['name']}  ({p['variant']})")
    for p in plan_reg: print(f"  registry {'clone' if p['pin'] else 'SKIP(no-pin!)'} {p['name']}  {p['url']}@{p['pin']}")
    for s in skipped:  print(f"  skip     {s}  (runtime 不匹配)")
    for u in undeclared: print(f"  skip     {u}  (未声明 target_runtimes；要装请写 [all] 或含本 runtime)")
    for n in reg_rejected: print(f"  REJECT   {n!r}  (非法 skill 名，疑似路径穿越——拒绝安装)")

    if dry:
        print(f"  → 计划 {len(plan_own)} own + {len(plan_reg)} registry（dry-run，未执行）")
        return 0

    os.makedirs(a.target, exist_ok=True)
    installed, failed = [], []
    for p in plan_own:
        dest = os.path.join(a.target, p["name"])
        if os.path.isdir(dest): shutil.rmtree(dest)
        shutil.copytree(p["src"], dest)
        if p["variant"] != "SKILL.md":  # 选中 runtime 变体 → 落地为 SKILL.md
            shutil.copyfile(os.path.join(dest, p["variant"]), os.path.join(dest, "SKILL.md"))
        installed.append({"name": p["name"], "source": "own", "variant": p["variant"]})
    for p in plan_reg:
        if not p["pin"]:
            print(f"  [SKIP] {p['name']} 无 pin，拒绝 clone（裸追上游有风险；请加 pin，如 pin: v1.2.0，或 pin: main + trusted_floating: true）")
            failed.append(p["name"]); continue
        dest = os.path.join(a.target, p["name"])
        if not (safe_name(p["name"]) and within_target(a.target, dest)):   # 兜底：dest 必须在 target 内
            print(f"  [REJECT] {p['name']!r} 安装目录越出 target，拒绝（路径穿越防护）")
            failed.append(p["name"]); continue
        try:
            if os.path.isdir(dest): shutil.rmtree(dest)
            subprocess.run(["git", "clone", "--depth", "1", p["url"], dest],
                           check=True, capture_output=True, text=True)
            # 钉到 pin：fetch + 检出 FETCH_HEAD；任一失败即安装失败（绝不静默停在默认分支）。
            subprocess.run(["git", "-C", dest, "fetch", "--depth", "1", "origin", p["pin"]],
                           check=True, capture_output=True, text=True)
            subprocess.run(["git", "-C", dest, "checkout", "--detach", "FETCH_HEAD"],
                           check=True, capture_output=True, text=True)
            commit = subprocess.run(["git", "-C", dest, "rev-parse", "HEAD"],
                                    check=True, capture_output=True, text=True).stdout.strip()
            shutil.rmtree(os.path.join(dest, ".git"), ignore_errors=True)  # 冻结为快照，杜绝 stray git pull 漂移
            installed.append({"name": p["name"], "source": "registry", "pin": p["pin"], "commit": commit})
            print(f"  [OK] registry {p['name']} @ {p['pin']} ({commit[:10]})")
        except subprocess.CalledProcessError as e:
            shutil.rmtree(dest, ignore_errors=True)   # 不留半截/错版本，也不记录到清单
            msg = (e.stderr or "").strip()
            last = msg.splitlines()[-1] if msg else str(e)
            print(f"  [FAIL] {p['name']} 安装失败（pin={p['pin']} 不可达或检出失败）：{last}")
            failed.append(p["name"])

    mpath = a.manifest or os.path.join(a.target, "installed-skills.json")
    json.dump({"runtime": a.runtime, "installed": installed}, open(mpath, "w"), ensure_ascii=False, indent=2)
    print(f"  → 装了 {len(installed)} 个；清单写入 {mpath}")
    if failed:
        print(f"  [WARN] {len(failed)} 个 registry 条目未安装: {failed}")
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
