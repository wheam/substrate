#!/usr/bin/env python3
"""substrate-runtime-context / wire-context — 通用「按 adapter 接常驻注入」（零依赖，python3 标准库）。

把「生成小抄 + 接进 runtime」做成 **runtime 中立**：核心代码不认任何 runtime 名，
一切差异从 `adapters/<runtime>/adapter.yaml` 的 `runtime_context:` 块读。这样 hermes / openclaw /
将来任何 agent 都走同一条通路——给它写个 adapter 块即可，核心零改动。

用法:
  python3 wire-context.py --instance <实例根> --runtime <名> [--adapters <目录>] [--apply]

行为（按 adapter 的 runtime_context 决定）:
  - 无 adapter / 无 runtime_context / default_on 非 true → 注入对该 runtime【默认关】，不写、退出 0。
    （claude-code / codex 这类不声明 runtime_context 的 runtime 天然落到这里。）
  - default_on: true → 生成小抄 → 写到 adapter 声明的 digest_file（--apply 才真写；默认 dry-run）。
    并打印「一次性接线指令」（inject_via，注入点因 runtime 而异，来自 adapter）。

退出码: 0 = 成功（含「默认关」）; 2 = 调用错误（缺参/路径不对）。
"""
import sys, os, re, subprocess

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))


def read_text(p):
    try:
        return open(p, encoding="utf-8-sig", errors="replace").read()
    except Exception:
        return None


def top_block(text, key):
    """取顶层 `key:`（其值在下方缩进的子块）下的缩进子块文本。无则 None。"""
    m = re.search(r"(?m)^%s:[ \t]*$" % re.escape(key), text)
    if not m:
        return None
    out = []
    for ln in text[m.end():].split("\n")[1:]:
        if ln.strip() == "":
            out.append(ln)
            continue
        if re.match(r"^[ \t]", ln):
            out.append(ln)
        else:
            break
    return "\n".join(out)


def scalar(block, key):
    """从子块里读缩进标量 `key: value`（剥行尾 `# 注释` 与引号）。无则 None。"""
    if not block:
        return None
    m = re.search(r"(?m)^[ \t]+%s:[ \t]*(.+?)[ \t]*$" % re.escape(key), block)
    if not m:
        return None
    v = re.split(r"\s+#", m.group(1).strip(), maxsplit=1)[0].strip().strip("'\"")
    return v


def render_digest(instance):
    """复用 render-context.py 生成小抄（继承其体积护栏告警）。失败返回 None。"""
    try:
        r = subprocess.run(
            [sys.executable, os.path.join(SKILL_DIR, "render-context.py"), instance],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
    except Exception:
        return None
    if r.stderr:
        sys.stderr.write(r.stderr.decode("utf-8", "replace"))
    if r.returncode != 0:
        return None
    return r.stdout.decode("utf-8", "replace")


def resolve_digest_path(rc_block):
    """digest 落地路径：env override 优先（adapter 声明的环境变量名），否则展开 digest_file 的 ~。"""
    env_key = scalar(rc_block, "digest_file_env_override")
    if env_key and os.environ.get(env_key):
        return os.path.expanduser(os.environ[env_key])
    df = scalar(rc_block, "digest_file")
    return os.path.expanduser(df) if df else None


def main(argv):
    args = {}
    apply = False
    it = iter(argv[1:])
    for a in it:
        if a == "--apply":
            apply = True
        elif a in ("--instance", "--runtime", "--adapters"):
            args[a.lstrip("-")] = next(it, None)
        else:
            sys.stderr.write("wire-context: 未知参数 %s\n" % a)
            return 2
    instance = args.get("instance")
    runtime = args.get("runtime")
    # 默认 <instance>/adapters：自包含实例由 init-instance.sh 把 adapters/ 一并 vendor 进实例，
    # 故 skill 里只需 --instance + --runtime，免传引擎路径。显式 --adapters 仍可覆盖。
    adapters = args.get("adapters") or (os.path.join(instance, "adapters") if instance else "adapters")
    if not instance or not runtime:
        sys.stderr.write("wire-context: 需 --instance <根> 与 --runtime <名>\n")
        return 2
    if not os.path.isdir(instance):
        sys.stderr.write("wire-context: 实例路径不是目录: %s\n" % instance)
        return 2

    atext = read_text(os.path.join(adapters, runtime, "adapter.yaml"))
    rc_block = top_block(atext, "runtime_context") if atext else None
    on = (scalar(rc_block, "default_on") == "true") if rc_block else False
    if not on:
        why = "无 adapter/未声明 runtime_context" if not rc_block else "default_on 非 true"
        print("[wire-context] 注入对 runtime '%s' 默认关（%s）——不写、跳过。" % (runtime, why))
        return 0

    digest = render_digest(instance)
    if digest is None:
        sys.stderr.write("wire-context: 生成小抄失败（render-context.py）。\n")
        return 2
    path = resolve_digest_path(rc_block)
    if not path:
        sys.stderr.write("wire-context: adapter 未声明 digest_file，无处落地。\n")
        return 2

    if apply:
        d = os.path.dirname(path)
        if d and not os.path.isdir(d):
            try:
                os.makedirs(d, exist_ok=True)
            except Exception as e:
                sys.stderr.write("wire-context: 建目录失败 %s: %s\n" % (d, e))
                return 2
        with open(path, "w", encoding="utf-8") as f:
            f.write(digest)
        print("[wire-context] runtime '%s'：注入【已开】，小抄（%d 字符）已刷新 → %s"
              % (runtime, len(digest), path))
    else:
        print("[wire-context] runtime '%s'：注入【开】(dry-run)，将写小抄（%d 字符）→ %s（加 --apply 真写）"
              % (runtime, len(digest), path))

    inject_via = scalar(rc_block, "inject_via")
    if inject_via:
        print("[wire-context] 一次性接线（注入点见 adapter）：让 %s 启动时加载该文件——%s" % (runtime, inject_via))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
