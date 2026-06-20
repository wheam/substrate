#!/usr/bin/env python3
"""substrate-sync — 按 runtime 选择性安装 skill + 写本地清单（零依赖）。

用法:
  python3 sync.py --src <skills目录> [--target <skill 目录>] \
                  --runtime claude-code [--registry <_registry.md>] [--apply]

默认 **dry-run**（只打计划，不动文件）；加 --apply 才真正拷贝/clone。
--target 省略时：从 adapters/<runtime>/adapter.yaml 推断安装目录（view-layer 的 adapter 会被拒绝）。
本地清单（installed-skills.json）写到 --target，**不入库**。
"""
import sys, os, re, json, shutil, argparse, subprocess

def field(text, key):
    m = re.search(rf"(?m)^{key}:\s*\[(.*?)\]", text)
    if m: return [x.strip() for x in m.group(1).split(",") if x.strip()]
    m = re.search(rf"(?m)^{key}:\s*\n((?:[ \t]*-[ \t]*.+\n?)+)", text)
    if m: return [re.sub(r"^[ \t]*-[ \t]*", "", l).strip() for l in m.group(1).splitlines() if l.strip()]
    return []

def manifest_of(skill_dir):
    sk = os.path.join(skill_dir, "SKILL.md")
    if not os.path.isfile(sk): return None
    t = open(sk, encoding="utf-8-sig", errors="replace").read()
    return {"target_runtimes": field(t, "target_runtimes") if t.lstrip().startswith("---") else []}

def selected(runtimes, runtime):
    return (not runtimes) or ("all" in runtimes) or (runtime in runtimes)

def parse_registry(path, runtime):
    if not path or not os.path.isfile(path): return []
    t = open(path, encoding="utf-8-sig", errors="replace").read()
    m = re.search(r"```yaml\n(.*?)```", t, re.S)
    block = "\n".join(l for l in (m.group(1) if m else "").splitlines() if not l.lstrip().startswith("#"))
    out = []
    for chunk in re.split(r"(?m)^\s*-\s+name:", block)[1:]:
        name = chunk.splitlines()[0].strip()
        url = (re.search(r"(?m)^\s*upstream_git_url:\s*(\S+)", chunk) or [None, None])[1]
        pinm = re.search(r"(?m)^\s*pin:\s*(\S+)", chunk)
        rts = field(chunk, "target_runtimes")   # 整块解析，含多行列表形式（避免 fail-open）
        if url and selected(rts, runtime):
            out.append({"name": name, "url": url, "pin": pinm.group(1) if pinm else None})
    return out

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
    plan_own, plan_reg, skipped = [], [], []

    for entry in sorted(os.listdir(a.src)):
        d = os.path.join(a.src, entry)
        man = manifest_of(d)
        if man is None: continue
        rts = man["target_runtimes"]
        if selected(rts, a.runtime):
            variant = f"SKILL.{a.runtime}.md"
            plan_own.append({"name": entry, "variant": variant if os.path.isfile(os.path.join(d, variant)) else "SKILL.md", "src": d})
        else:
            skipped.append(entry)

    plan_reg = parse_registry(a.registry, a.runtime)

    print(f"substrate-sync  runtime={a.runtime}  target={a.target}  mode={'DRY-RUN' if dry else 'APPLY'}")
    for p in plan_own: print(f"  own      install {p['name']}  ({p['variant']})")
    for p in plan_reg: print(f"  registry {'clone' if p['pin'] else 'CLONE(no-pin!)'} {p['name']}  {p['url']}@{p['pin']}")
    for s in skipped:  print(f"  skip     {s}  (runtime 不匹配)")

    if dry:
        print(f"  → 计划 {len(plan_own)} own + {len(plan_reg)} registry（dry-run，未执行）")
        return 0

    os.makedirs(a.target, exist_ok=True)
    installed = []
    for p in plan_own:
        dest = os.path.join(a.target, p["name"])
        if os.path.isdir(dest): shutil.rmtree(dest)
        shutil.copytree(p["src"], dest)
        if p["variant"] != "SKILL.md":  # 选中 runtime 变体 → 落地为 SKILL.md
            shutil.copyfile(os.path.join(dest, p["variant"]), os.path.join(dest, "SKILL.md"))
        installed.append({"name": p["name"], "source": "own", "variant": p["variant"]})
    for p in plan_reg:
        if not p["pin"]:
            print(f"  [SKIP] {p['name']} 无 pin，拒绝 clone（裸追上游有风险；请加 pin）")
            continue
        dest = os.path.join(a.target, p["name"])
        try:
            if os.path.isdir(dest): shutil.rmtree(dest)
            subprocess.run(["git", "clone", "--depth", "1", p["url"], dest], check=True)
            if p["pin"]:
                subprocess.run(["git", "-C", dest, "fetch", "--depth", "1", "origin", p["pin"]], check=False)
                subprocess.run(["git", "-C", dest, "checkout", p["pin"]], check=False)
            installed.append({"name": p["name"], "source": "registry", "pin": p["pin"]})
        except Exception as e:
            print(f"  [WARN] clone 失败 {p['name']}: {e}")

    mpath = a.manifest or os.path.join(a.target, "installed-skills.json")
    json.dump({"runtime": a.runtime, "installed": installed}, open(mpath, "w"), ensure_ascii=False, indent=2)
    print(f"  → 装了 {len(installed)} 个；清单写入 {mpath}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
