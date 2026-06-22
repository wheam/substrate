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
    is_fm = t.lstrip().startswith("---")
    sup = re.search(r"(?m)^superseded_by:\s*(\S+)", t) if is_fm else None
    return {"target_runtimes": field(t, "target_runtimes") if is_fm else [],
            "deprecated": bool(re.search(r"(?m)^deprecated:\s*true\b", t)) if is_fm else False,
            "superseded_by": (sup.group(1).strip("'\"") if sup else None)}

def selected(runtimes, runtime):
    """fail-closed：未声明 target_runtimes（[]）不算选中。要全 runtime 显式写 [all]。"""
    return ("all" in runtimes) or (runtime in runtimes)

def parse_registry(path, runtime):
    """返回 (git_entries, plugins, undeclared, rejected)。
    git_entries=kind:git 且选中本 runtime（待 clone）；plugins=kind:plugin（插件机制管理，sync 不 clone，仅登记）；
    undeclared=未声明 target_runtimes 的；rejected=skill 名非法（路径穿越防护）的。"""
    if not path or not os.path.isfile(path): return [], [], [], []
    t = open(path, encoding="utf-8-sig", errors="replace").read()
    m = re.search(r"```yaml\n(.*?)```", t, re.S)
    block = "\n".join(l for l in (m.group(1) if m else "").splitlines() if not l.lstrip().startswith("#"))
    out, plugins, undeclared, rejected = [], [], [], []
    for chunk in re.split(r"(?m)^\s*-\s+name:", block)[1:]:
        name = chunk.splitlines()[0].strip().strip("'\"")
        kindm = re.search(r"(?m)^\s*kind:\s*(\S+)", chunk)
        kind = (kindm.group(1).strip("'\"") if kindm else "git")
        rts = field(chunk, "target_runtimes")   # 整块解析，含缩进/多行列表形式
        if not safe_name(name):
            rejected.append(name); continue       # 防路径穿越：非法 skill 名直接拒绝
        if not rts:
            undeclared.append(name); continue    # fail-closed：未声明 target_runtimes 不装
        if not selected(rts, runtime):
            continue
        if kind == "plugin":
            src = (re.search(r"(?m)^\s*source:\s*(.+?)\s*$", chunk) or [None, None])[1]
            plugins.append({"name": name, "source": (src.strip().strip("'\"") if src else None)})
            continue
        url = (re.search(r"(?m)^\s*upstream_git_url:\s*(\S+)", chunk) or [None, None])[1]
        pinm = re.search(r"(?m)^\s*pin:\s*(\S+)", chunk)
        if not url:
            continue
        out.append({"name": name, "url": url, "pin": pinm.group(1) if pinm else None})
    return out, plugins, undeclared, rejected

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

def instance_commit(src):
    """实例仓库 HEAD commit（信息性：记录"在哪个版本装的"）。非 git 返回 None。"""
    inst = os.path.dirname(os.path.abspath(src))
    try:
        r = subprocess.run(["git", "-C", inst, "rev-parse", "HEAD"], capture_output=True, text=True)
        return r.stdout.strip() if r.returncode == 0 else None
    except Exception:
        return None


def skills_tree(src):
    """实例 skills/ 子树的 git 对象哈希——**只在 skill 内容变化时才变**（漂移检测用）。
    这样每次普通内容提交（改知识页等、没动 skill）不会误报"该重 sync"。--src 的 basename 即子树名。"""
    inst = os.path.dirname(os.path.abspath(src))
    rel = os.path.basename(os.path.abspath(src))
    try:
        r = subprocess.run(["git", "-C", inst, "rev-parse", f"HEAD:{rel}"], capture_output=True, text=True)
        return r.stdout.strip() if r.returncode == 0 else None
    except Exception:
        return None


def remote_status(src, timeout=20):
    """Best-effort 远程比对：实例仓库本地 HEAD 是否落后其上游。返回 (kind, behind)：
      ('no-upstream', 0)  没配上游（纯本地库）——跳过，不提示。
      ('unreachable', 0)  有上游但联系不上远程——提示无法确认，但不报错。
      ('ok', n)           能比对，本地落后远程 n 个 commit。
    意义：即便 git pull 静默失败（权限/网络），--check 自己 fetch 后仍能发现"我落后了"，
    不再拿没更新的工作树误报"已对齐"。无 git/无上游/超时/异常一律非致命。"""
    inst = os.path.dirname(os.path.abspath(src))
    try:
        u = subprocess.run(["git", "-C", inst, "rev-parse", "--abbrev-ref", "@{u}"],
                           capture_output=True, text=True)
        if u.returncode != 0:
            return ("no-upstream", 0)
        f = subprocess.run(["git", "-C", inst, "fetch", "-q"],
                           capture_output=True, text=True, timeout=timeout)
        if f.returncode != 0:
            return ("unreachable", 0)
        r = subprocess.run(["git", "-C", inst, "rev-list", "--count", "HEAD..@{u}"],
                           capture_output=True, text=True)
        if r.returncode != 0:
            return ("unreachable", 0)
        return ("ok", int(r.stdout.strip() or "0"))
    except Exception:
        return ("unreachable", 0)


def do_check(a):
    """检测本机已装 skill 是否与实例对齐：比对清单记录的 instance_commit vs 实例当前 HEAD，
    并列出实例 skills/ 里选中本 runtime、但本机未安装的 skill。
    还会 best-effort fetch 比对本地 vs 远程上游——落后远程也算不对齐（堵"pull 没成功却报对齐"）。
    退出码: 0=已对齐; 1=有漂移（该 git pull / sync --apply）; 2=没装过/清单缺失或损坏。"""
    mpath = a.manifest or os.path.join(a.target, "installed-skills.json")
    if not os.path.isfile(mpath):
        print(f"substrate-sync --check: 没找到安装清单 {mpath}——本 runtime 还没装过，请先 --apply。")
        return 2
    try:
        man = json.load(open(mpath, encoding="utf-8"))
    except Exception as e:
        print(f"substrate-sync --check: 清单损坏 {mpath}: {e}"); return 2
    rec_tree = man.get("skills_tree")
    cur_tree = skills_tree(a.src)
    installed_names = {s.get("name") for s in man.get("installed", [])}
    src_names = set()
    retired_present = []
    for entry in sorted(os.listdir(a.src)):
        m = manifest_of(os.path.join(a.src, entry))
        if not m: continue
        if m["deprecated"] or m["superseded_by"]:
            if os.path.isdir(os.path.join(a.target, entry)):
                retired_present.append(entry)   # 退役但本机还残留 → 该 --apply 清掉
        elif selected(m["target_runtimes"], a.runtime):
            src_names.add(entry)
    missing = sorted(src_names - installed_names)

    rkind, behind = remote_status(a.src)

    print(f"substrate-sync --check  runtime={a.runtime}")
    print(f"  装机时实例 commit: {man.get('instance_commit') or '(未记录)'}")
    print(f"  skills/ 子树: 装机 {(rec_tree or '(未记录)')[:10]}  当前 {(cur_tree or '(非 git)')[:10]}")
    if rkind == "ok":
        print(f"  远程: 本地{'落后 origin %d 个 commit' % behind if behind else '与 origin 一致'}")
    elif rkind == "unreachable":
        print("  远程: 未能联系远程，无法确认是否落后（仅本地比对）")
    drift = []
    if rkind == "ok" and behind > 0:
        drift.append(f"本地仓库落后远程 {behind} 个 commit（git pull 可能没成功/没跑）——先 git pull 再对齐")
    if cur_tree and rec_tree and cur_tree != rec_tree:
        drift.append("skills/ 自上次同步后有变化（skill 更新/版本升级）——本机 skill 可能过时")
    if cur_tree and not rec_tree:
        drift.append("清单未记录 skills_tree（旧版 sync 装的）——建议重 sync 以登记版本")
    if missing:
        drift.append(f"实例有 {len(missing)} 个未安装的 skill: {missing}")
    if retired_present:
        drift.append(f"{len(retired_present)} 个已退役 skill 仍在本机: {retired_present}（sync --apply 会移除）")
    if drift:
        for d in drift:
            print(f"  ⚠ {d}")
        print(f"  → 不对齐：先 git pull（若落后远程），再 python3 {os.path.basename(__file__)} --src {a.src} --runtime {a.runtime} --apply  对齐。")
        return 1
    print("  ✓ 已对齐（已装 skill 与实例当前版本一致）。")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=".")
    ap.add_argument("--target")            # 省略则从 adapters/<runtime>/adapter.yaml 推断
    ap.add_argument("--runtime", default="claude-code")
    ap.add_argument("--adapters-dir")      # 默认 = 引擎 adapters/（按本脚本位置推断）
    ap.add_argument("--registry")
    ap.add_argument("--manifest")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--check", action="store_true", help="只检测：本机已装 skill 是否与实例当前版本对齐（不安装）")
    a = ap.parse_args()
    if not os.path.isdir(a.src):
        print(f"substrate-sync: --src 不是目录: {a.src}"); return 2
    if not a.target:
        if a.adapters_dir:
            cands = [a.adapters_dir]
        else:
            # 优先按【实例】推断：--src 是 <instance>/skills，adapters/ 是它的同级目录。
            # 这样不管 sync.py 待在引擎里、被 vendor 进自包含实例、还是 seed 到 runtime 的 skill 目录，
            # 只要 --src 指向一个带同级 adapters/ 的 skills 目录就能定位（修 MAJOR：旧实现只按
            # __file__ 上跳三级，自包含实例/seed 场景下 adapters/ 不在那 → 推断失败 exit 2）。
            # 兜底再按本脚本相对引擎布局（旧行为），覆盖 --src 无同级 adapters 的情形。
            cands = [
                os.path.join(os.path.dirname(os.path.abspath(a.src)), "adapters"),
                os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "adapters"),
            ]
        adir = next((c for c in cands if os.path.isfile(os.path.join(c, a.runtime, "adapter.yaml"))), cands[0])
        a.target, err = adapter_target(adir, a.runtime)
        if err:
            print(f"substrate-sync: {err}"); return 2
        print(f"  (--target 未给：从 adapter 推断为 {a.target})")
    if a.check:
        return do_check(a)
    dry = not a.apply
    plan_own, plan_reg, skipped, undeclared, retired = [], [], [], [], []

    for entry in sorted(os.listdir(a.src)):
        d = os.path.join(a.src, entry)
        man = manifest_of(d)
        if man is None: continue
        if man["deprecated"] or man["superseded_by"]:
            retired.append({"name": entry, "superseded_by": man["superseded_by"]})  # 退役件：不装，且从 target 清掉旧副本
            continue
        rts = man["target_runtimes"]
        if not rts:
            undeclared.append(entry)             # fail-closed：未声明 target_runtimes，不装
        elif selected(rts, a.runtime):
            variant = f"SKILL.{a.runtime}.md"
            plan_own.append({"name": entry, "variant": variant if os.path.isfile(os.path.join(d, variant)) else "SKILL.md", "src": d})
        else:
            skipped.append(entry)

    plan_reg, plugins, reg_undeclared, reg_rejected = parse_registry(a.registry, a.runtime)
    undeclared += [f"registry:{n}" for n in reg_undeclared]

    print(f"substrate-sync  runtime={a.runtime}  target={a.target}  mode={'DRY-RUN' if dry else 'APPLY'}")
    for p in plan_own: print(f"  own      install {p['name']}  ({p['variant']})")
    for p in plan_reg: print(f"  registry {'clone' if p['pin'] else 'SKIP(no-pin!)'} {p['name']}  {p['url']}@{p['pin']}")
    for p in plugins:  print(f"  plugin   {p['name']}  (kind=plugin；由插件机制管理，sync 不安装/更新；source={p['source'] or '?'})")
    for s in skipped:  print(f"  skip     {s}  (runtime 不匹配)")
    for u in undeclared: print(f"  skip     {u}  (未声明 target_runtimes；要装请写 [all] 或含本 runtime)")
    for n in reg_rejected: print(f"  REJECT   {n!r}  (非法 skill 名，疑似路径穿越——拒绝安装)")
    for r in retired:
        sb = f"，superseded_by {r['superseded_by']}" if r["superseded_by"] else ""
        here = os.path.isdir(os.path.join(a.target, r["name"]))
        print(f"  retire   {r['name']}  (已退役{sb}；{'从 target 移除旧副本' if here else '不安装'})")

    if dry:
        print(f"  → 计划 {len(plan_own)} own + {len(plan_reg)} registry-git"
              + (f"（另 {len(plugins)} 个 kind=plugin 不由 sync 装）" if plugins else "")
              + "（dry-run，未执行）")
        return 0

    os.makedirs(a.target, exist_ok=True)
    installed, failed, removed = [], [], []
    for r in retired:   # 退役 skill：从 target 清掉旧副本（防 personal-wiki 式陈旧、冲突的残留）
        dest = os.path.join(a.target, r["name"])
        if os.path.isdir(dest) and safe_name(r["name"]) and within_target(a.target, dest):
            shutil.rmtree(dest, ignore_errors=True)
            removed.append(r["name"])
    if removed:
        print(f"  [RETIRE] 移除已退役 skill: {removed}")
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
    json.dump({"runtime": a.runtime, "instance_commit": instance_commit(a.src),
               "skills_tree": skills_tree(a.src), "installed": installed},
              open(mpath, "w"), ensure_ascii=False, indent=2)
    print(f"  → 装了 {len(installed)} 个；清单写入 {mpath}")
    if failed:
        print(f"  [WARN] {len(failed)} 个 registry 条目未安装: {failed}")
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
