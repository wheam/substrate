#!/usr/bin/env python3
"""substrate-migrate — 跨引擎版本安全迁移（零依赖，python3 标准库）。

把"引擎版本升级"当数据库迁移做：有序 / 命名 / 幂等 / 可验证 / 可回滚 / 不丢数据。
实现 BUILD-PLAN §9 的流程。**只对传入的【实例路径】操作**。

用法:
  python3 migrate.py --instance <实例根> --engine <引擎根> [--apply]
                     [--doctor <doctor.py 路径>] [--leader] [--yes]

  --instance   要迁移的实例根目录（含 governance/SUBSTRATE_VERSION）。必填。
  --engine     引擎根目录（含 ENGINE_VERSION + migrations/）。默认 = 本脚本所在仓库根。
  --apply      真正执行（打 tag / 改文件 / bump 版本）。**省略即 dry-run**：只生成并打印迁移计划。
  --doctor     substrate-doctor 的 doctor.py 路径。默认按引擎布局推断。
  --leader     声明本机是 fleet 的 migration_leader（多机协调；仅记录到报告，不改行为）。
  --yes        跳过"是否继续"的交互确认（用于非交互/CI；交互场景由 agent/人确认）。

退出码:
  0 = 成功（已最新而跳过 / dry-run 出计划 / apply 全部迁移成功）
  1 = 迁移失败（某步 verify 或 doctor 不变量不过 → 已回滚到 pre-migrate tag → 转人工）
  2 = 调用错误（路径不对 / 拒绝在引擎本体上跑 / 缺 git 仓库 / 迁移文件损坏）

安全护栏（关键）:
  - 若 --instance 根存在 ENGINE_VERSION 文件 → 这是引擎本体而非实例 → **拒绝运行**（退出 2）。
  - apply 模式要求 --instance 是一个 **干净的 git 仓库**（无未提交改动），否则拒绝（保证 tag 快照与回滚可靠）。
  - 一切破坏性 git 操作（tag / reset --hard）只在 --instance 上执行，引擎仓库绝不被碰。

零依赖约束: 版本/迁移元信息用受限子集正则解析（不假设 PyYAML）。
"""
import sys, os, re, glob, argparse, subprocess


# ── 工具 ────────────────────────────────────────────────────────────────────

def read_text(p):
    try:
        return open(p, encoding="utf-8-sig", errors="replace").read()
    except Exception:
        return None


def parse_version(s):
    """'1.2.3' → (1,2,3)；非数字段当 0；坏输入返回 None。"""
    if s is None:
        return None
    s = s.strip().lstrip("vV")
    parts = re.findall(r"\d+", s)
    if not parts:
        return None
    return tuple(int(x) for x in parts[:3]) + (0,) * (3 - len(parts[:3]))


def yaml_scalar(text, key):
    """从受限子集 YAML 文本取标量 key 的值（支持 'k: v' 与多行 >-/| 折叠块）。"""
    # 折叠/字面块: key: >- \n   缩进续行
    m = re.search(rf"(?m)^{re.escape(key)}[ \t]*:[ \t]*[>|][-+]?[ \t]*\n((?:[ \t]+.*\n?)+)", text)
    if m:
        return " ".join(l.strip() for l in m.group(1).splitlines() if l.strip())
    m = re.search(rf"(?m)^{re.escape(key)}[ \t]*:[ \t]*(.+)$", text)
    if m:
        return m.group(1).strip().strip('"').strip("'")
    return None


def git(instance, *cargs, check=True):
    """在实例仓库内跑 git。返回 CompletedProcess。"""
    return subprocess.run(
        ["git", "-C", instance, *cargs],
        check=check, capture_output=True, text=True,
    )


def is_git_repo(path):
    try:
        r = git(path, "rev-parse", "--is-inside-work-tree", check=False)
        return r.returncode == 0 and r.stdout.strip() == "true"
    except Exception:
        return False


def is_clean(instance):
    r = git(instance, "status", "--porcelain", check=False)
    return r.returncode == 0 and r.stdout.strip() == ""


def md_count(instance):
    """实例内 .md 文件数（直接数，不去刮 doctor 的自由文本输出）。迁移不变量：不减少。"""
    return len(glob.glob(os.path.join(instance, "**", "*.md"), recursive=True))


# ── 发现迁移 ─────────────────────────────────────────────────────────────────

def load_migration(mdir):
    """读一个 migrations/<id>/migration.yaml；返回元信息 dict 或 None（损坏）。"""
    yml = os.path.join(mdir, "migration.yaml")
    text = read_text(yml)
    if text is None:
        return None
    mid = yaml_scalar(text, "id")
    fv = yaml_scalar(text, "from_version")
    tv = yaml_scalar(text, "to_version")
    title = yaml_scalar(text, "title")
    if not (mid and fv and tv):
        return None
    # 契约校验（schemas/migration.schema.yaml 必填）：steps 与 idempotent:true 必须在场，
    # 否则视为损坏迁移（discover 会据此拒绝继续，不静默跳过）。
    if not re.search(r"(?m)^[ \t]*idempotent[ \t]*:[ \t]*true\b", text):
        return None
    if not re.search(r"(?m)^[ \t]*steps[ \t]*:", text):
        return None
    return {
        "id": mid,
        "dir": mdir,
        "from": fv,
        "to": tv,
        "from_t": parse_version(fv),
        "to_t": parse_version(tv),
        "title": title or mid,
        "risk": yaml_scalar(text, "risk_level") or "unknown",
        "apply_py": os.path.join(mdir, "apply.py"),
    }


def discover(engine, inst_v_t, eng_v_t):
    """返回区间 (inst_v, eng_v] 内的 pending 迁移，按 from_version 升序、再按目录 id 升序。

    一个迁移 pending 当且仅当 inst_v <= from_version 且 to_version <= eng_v。
    （等号在 from 侧：实例正处于该迁移的起点版本，该迁移待应用。）
    """
    migdir = os.path.join(engine, "migrations")
    out, broken = [], []
    if not os.path.isdir(migdir):
        return out, broken
    for d in sorted(glob.glob(os.path.join(migdir, "*"))):
        if not os.path.isdir(d):
            continue
        if not os.path.isfile(os.path.join(d, "migration.yaml")):
            continue
        meta = load_migration(d)
        if meta is None or meta["from_t"] is None or meta["to_t"] is None:
            broken.append(os.path.basename(d))
            continue
        if meta["from_t"] >= inst_v_t and meta["to_t"] <= eng_v_t:
            out.append(meta)
    out.sort(key=lambda m: (m["from_t"], os.path.basename(m["dir"])))
    return out, broken


# ── doctor 不变量快照 ────────────────────────────────────────────────────────

def doctor_snapshot(doctor_py, instance):
    """跑 doctor.py，返回 (exit_code, md_count, zone_ids, stdout)。

    md_count / zone_ids 是要在迁移前后保持的关键不变量。doctor 退出码非 0 也照常返回，
    由调用方决定如何用（迁移后必须 0 error）。
    """
    r = subprocess.run(
        ["python3", doctor_py, instance], check=False, capture_output=True, text=True,
    )
    out = r.stdout or ""
    m = re.search(r"\((\d+)\s*md", out)
    md = int(m.group(1)) if m else None
    zones = zone_ids(instance)
    return r.returncode, md, zones, out


def zone_ids(instance):
    """从实例 governance/zones.md 的 YAML 块抽 zone id 集合（不变量：注册不丢）。"""
    z = os.path.join(instance, "governance", "zones.md")
    text = read_text(z)
    if text is None:
        return set()
    m = re.search(r"```yaml\n(.*?)```", text, re.S)
    block = m.group(1) if m else text
    return set(re.findall(r"(?m)^\s*-\s+id:\s*(\S+)", block))


# ── 版本文件 ─────────────────────────────────────────────────────────────────

def instance_version_path(instance):
    return os.path.join(instance, "governance", "SUBSTRATE_VERSION")


def write_instance_version(instance, ver):
    p = instance_version_path(instance)
    with open(p, "w", encoding="utf-8") as f:
        f.write(ver.strip() + "\n")


# ── 主流程 ───────────────────────────────────────────────────────────────────

def run_one(meta, instance, doctor_py, log):
    """应用单个迁移（已在 apply 模式 + tag 已打）。成功返回 True；失败回滚并返回 False。"""
    mid = meta["id"]
    tag = f"pre-migrate-{meta['from']}"

    def rollback(reason):
        log(f"  [FAIL] {mid}: {reason}")
        log(f"  回滚: git reset --hard {tag} && git clean -fd")
        r = git(instance, "reset", "--hard", tag, check=False)
        git(instance, "clean", "-fd", check=False)   # 清掉失败 apply 创建的未跟踪文件（迁移前工作区是干净的，残留必是本次产生）
        if r.returncode != 0:
            log(f"  [ERROR] 回滚失败！请人工 `git -C {instance} reset --hard {tag} && git clean -fd`. stderr={r.stderr.strip()}")
        else:
            log(f"  已回滚到 {tag}（含清理未跟踪残留），可安全重试。转人工审查。")

    # 迁移前 doctor 快照（md 计数直接数文件，不依赖 doctor stdout 文案）
    pre_code, _, pre_zones, _ = doctor_snapshot(doctor_py, instance)
    pre_md = md_count(instance)
    log(f"  迁移前 doctor: exit={pre_code} md={pre_md} zones={sorted(pre_zones)}")

    # 应用变换（幂等）
    if not os.path.isfile(meta["apply_py"]):
        rollback(f"找不到 apply.py: {meta['apply_py']}")
        return False
    ar = subprocess.run(
        ["python3", meta["apply_py"], instance, "--apply"],
        check=False, capture_output=True, text=True,
    )
    for l in (ar.stdout or "").splitlines():
        log(f"    apply| {l}")
    if ar.returncode != 0:
        rollback(f"apply 退出码 {ar.returncode}\n{ar.stderr.strip()}")
        return False

    # 该迁移自带 verify（apply.py --check）
    vr = subprocess.run(
        ["python3", meta["apply_py"], instance, "--check"],
        check=False, capture_output=True, text=True,
    )
    for l in (vr.stdout or "").splitlines():
        log(f"    verify| {l}")
    if vr.returncode != 0:
        rollback(f"verify 失败（退出码 {vr.returncode}）")
        return False

    # 迁移后 doctor + 不变量对比
    post_code, _, post_zones, post_out = doctor_snapshot(doctor_py, instance)
    post_md = md_count(instance)
    log(f"  迁移后 doctor: exit={post_code} md={post_md} zones={sorted(post_zones)}")
    if post_code not in (0,):
        # 迁移后必须 0 error（doctor 退出 2 = 调用错误也算失败）
        rollback(f"迁移后 doctor 非 0（exit={post_code}），有 error 或调用错误:\n{post_out}")
        return False
    if post_md < pre_md:
        rollback(f"md 文件数减少 {pre_md} → {post_md}（疑似丢失内容页）。增/拆文件允许，删减不允许。")
        return False
    lost = pre_zones - post_zones
    if lost:
        rollback(f"zone 注册丢失: {sorted(lost)}")
        return False

    # 成功 → bump 实例版本
    write_instance_version(instance, meta["to"])
    log(f"  [OK] {mid}: 已 bump SUBSTRATE_VERSION → {meta['to']}")
    return True


def fetch_remote_text(url, timeout=10):
    """Best-effort 取一个小文本文件内容（http/https/file）。失败返回 None。仅标准库。"""
    try:
        import urllib.request
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.read().decode("utf-8", "replace")
    except Exception:
        return None


def remote_engine_note(instance, inst_v_t, log):
    """Fix3（纯提醒，永不致命）：读 instance 的 governance/ENGINE_SOURCE_URL
    （一行：指向远程引擎 ENGINE_VERSION 的 URL，可由 init-instance 写入），best-effort
    取远程引擎版本——比实例新则提醒「去 migration_leader 升级」。无该文件/取不到/解析不了
    一律静默或软提示。无引擎的 agent 也能借此知道引擎出新版了（但升级仍在 leader 上做）。"""
    url_raw = read_text(os.path.join(instance, "governance", "ENGINE_SOURCE_URL"))
    if not url_raw or not url_raw.strip():
        return
    url = url_raw.strip().splitlines()[0].strip()
    if not url:
        return
    remote = fetch_remote_text(url)
    if remote is None:
        log(f"  远程引擎版本：未能联系 {url}（跳过提醒）")
        return
    rv_t = parse_version(remote)
    if rv_t is None:
        return
    if inst_v_t is not None and rv_t > inst_v_t:
        log(f"  ⚠ 引擎有新版 {remote.strip()}（你的实例更早）——到 migration_leader（有引擎的机器）上跑 substrate-migrate 升级，其它机器随后 pull 实例即可。")
    else:
        log(f"  引擎远程版本 {remote.strip()}：实例已跟上。")


def main(argv):
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--instance", required=True)
    ap.add_argument("--engine")
    ap.add_argument("--doctor")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--leader", action="store_true")
    ap.add_argument("--yes", action="store_true")
    a = ap.parse_args(argv)

    out_lines = []
    def log(m):
        out_lines.append(m)
        print(m)

    instance = os.path.abspath(a.instance)
    if not os.path.isdir(instance):
        print(f"substrate-migrate: --instance 不是目录: {instance}")
        return 2

    # ── 安全护栏 1: 拒绝在引擎本体上跑 ──
    if os.path.isfile(os.path.join(instance, "ENGINE_VERSION")):
        print(f"substrate-migrate: 拒绝运行——目标根存在 ENGINE_VERSION，这是【引擎本体】而非实例。")
        print(f"  迁移只能跑在用户实例上（实例的版本记在 governance/SUBSTRATE_VERSION）。")
        return 2

    # 实例版本（先读：远程提醒 + 无引擎跳过都要用）
    inst_ver = read_text(instance_version_path(instance))
    if inst_ver is None:
        print(f"substrate-migrate: 找不到实例 SUBSTRATE_VERSION: {instance_version_path(instance)}")
        return 2
    inst_v_t = parse_version(inst_ver)
    if inst_v_t is None:
        print(f"substrate-migrate: 实例版本号无法解析（instance={inst_ver!r}）")
        return 2

    # Fix3：可选的远程引擎版本提醒（纯提醒，永不致命）
    remote_engine_note(instance, inst_v_t, log)

    # 引擎根：显式 --engine，或默认本脚本所在仓库（skills/substrate-migrate/.. → 引擎根）
    engine_explicit = a.engine is not None
    engine = os.path.abspath(a.engine) if a.engine else os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..")
    )
    eng_ver_path = os.path.join(engine, "ENGINE_VERSION")
    eng_ver = read_text(eng_ver_path)
    if eng_ver is None:
        if engine_explicit:
            # 用户显式 --engine 指到了没有 ENGINE_VERSION 的地方 → 真错误
            print(f"substrate-migrate: 找不到引擎 ENGINE_VERSION: {eng_ver_path}（--engine 指错了？）")
            return 2
        # Fix1：本机没有引擎仓库（自包含实例）——这是常态，不是错误。
        # 迁移脚本只在引擎里（不 vendor 进实例），所以跨版本升级只在有引擎的机器（migration_leader）上做；
        # 其它机器随后 pull 已迁好的实例 + sync 重对齐即可。
        log(f"substrate-migrate: 本机无引擎仓库（自包含实例）——跳过迁移检查（正常）。")
        log(f"  实例 SUBSTRATE_VERSION={inst_ver.strip()}；跨版本升级在 migration_leader（有引擎）上跑。")
        return 0
    eng_v_t = parse_version(eng_ver)
    if eng_v_t is None:
        print(f"substrate-migrate: 引擎版本号无法解析（engine={eng_ver!r}）")
        return 2

    # doctor 路径
    doctor_py = os.path.abspath(a.doctor) if a.doctor else os.path.join(
        engine, "skills", "substrate-doctor", "doctor.py"
    )
    if not os.path.isfile(doctor_py):
        print(f"substrate-migrate: 找不到 doctor.py: {doctor_py}（用 --doctor 指定）")
        return 2

    log(f"substrate-migrate")
    log(f"  实例: {instance}  (SUBSTRATE_VERSION={inst_ver.strip()})")
    log(f"  引擎: {engine}  (ENGINE_VERSION={eng_ver.strip()})")
    if a.leader:
        log(f"  本机声明为 migration_leader")

    # ── 版本闸门（多机幂等）: 已最新即跳过 ──
    if inst_v_t >= eng_v_t:
        log(f"  → 实例已是最新（{inst_ver.strip()} >= {eng_ver.strip()}），无 pending 迁移，跳过。")
        return 0

    # ── 发现 pending 迁移 ──
    pending, broken = discover(engine, inst_v_t, eng_v_t)
    if broken:
        log(f"  [ERROR] 以下迁移文件损坏/缺字段，拒绝继续: {broken}")
        return 2
    if not pending:
        log(f"  → 区间 ({inst_ver.strip()}, {eng_ver.strip()}] 内无可用迁移；")
        log(f"     但版本落后于引擎——可能缺迁移脚本。转人工核对引擎 migrations/。")
        return 1

    # ── 生成迁移计划（不静默执行，先呈现）──
    log(f"  迁移计划（{len(pending)} 个，按序）:")
    cur = inst_ver.strip()
    for m in pending:
        log(f"    [{m['id']}] {m['from']} → {m['to']}  risk={m['risk']}  {m['title']}")
    log(f"  路径: {cur} → " + " → ".join(m["to"] for m in pending))

    # 校验链条连续（每个迁移的 from 应等于上一个的 to，起点等于实例当前版本）
    chain_from = inst_v_t
    for m in pending:
        if m["from_t"] != chain_from:
            log(f"  [WARN] 迁移链不连续: 期望 from={chain_from}，但 {m['id']} from={m['from']}。")
            log(f"         可能缺中间迁移，请人工核对。")
            return 1
        chain_from = m["to_t"]

    # 链条必须抵达引擎版本，否则即使全部应用，实例仍落后于引擎却会被报成功。
    if chain_from != eng_v_t:
        log(f"  [ERROR] 迁移链未抵达引擎版本：链止于 {pending[-1]['to']}，但 ENGINE_VERSION={eng_ver.strip()}。")
        log(f"          区间内缺少抵达引擎版本的迁移；拒绝继续（避免迁完仍落后却报成功）。请人工核对引擎 migrations/。")
        return 1

    if not a.apply:
        log(f"  → DRY-RUN：以上为迁移计划，未执行。确认后加 --apply 真正迁移。")
        return 0

    # ── apply 前置: 必须是干净 git 仓库 ──
    if not is_git_repo(instance):
        log(f"  [ERROR] 实例不是 git 仓库；迁移依赖 git tag 做回滚点。请先 git init + 提交。")
        return 2
    if not is_clean(instance):
        log(f"  [ERROR] 实例有未提交改动；为保证回滚可靠，请先提交或 stash 后再迁移。")
        return 2

    # ── apply 前置: 迁移前 doctor 必须干净，否则既有问题会被误判成迁移失败 ──
    pf_code, _, _, pf_out = doctor_snapshot(doctor_py, instance)
    if pf_code != 0:
        log(f"  [ERROR] 迁移前 doctor 未通过（exit={pf_code}）；请先修复既有问题再迁移：\n{pf_out}")
        return 2

    if not a.yes:
        # 真正的确认闸门：交互场景提示输入 yes；非交互（CI/agent）必须显式 --yes，否则中止不执行。
        if sys.stdin.isatty():
            try:
                ans = input("  确认执行以上迁移计划？输入 yes 继续: ").strip().lower()
            except EOFError:
                ans = ""
            if ans not in ("yes", "y"):
                log("  已取消：未确认（未做任何改动）。")
                return 0
        else:
            log("  [中止] 非交互环境需显式 --yes 确认。已展示迁移计划，复核后加 --yes 重跑。")
            return 2

    # ── 按序应用，每个 = tag → apply → verify → doctor 前后对比 ──
    for m in pending:
        mid = m["id"]
        tag = f"pre-migrate-{m['from']}"
        log(f"  ── 应用 {mid} ({m['from']} → {m['to']}) ──")

        # 备份 tag：总是用 -f 把 tag（重）指向**当前 HEAD = 本次迁移前的真实状态**。
        # 关键修复（防数据丢失）：tag 以版本号命名，跨多次运行会变陈旧；旧实现「已存在就复用」
        # 会让失败回滚 `git reset --hard <陈旧tag>` 吞掉两次运行之间操作者新提交的内容。
        # 每次都重指到 HEAD，保证回滚点永远是「本次迁移前」而非某次历史快照。
        r = git(instance, "tag", "-f", tag, check=False)
        if r.returncode != 0:
            log(f"  [ERROR] 打 tag 失败: {r.stderr.strip()}；中止。")
            return 2
        log(f"  备份: git tag -f {tag}（指向当前 HEAD）")

        ok = run_one(m, instance, doctor_py, log)
        if not ok:
            done = [x["id"] for x in pending[:pending.index(m)]]
            log(f"  迁移在 {mid} 失败并已回滚到其 pre-migrate tag。")
            if done:
                log(f"  注意：先前迁移 {done} 已成功并各自 commit，实例停在中间版本 {m['from']}（非原始版本）。")
            else:
                log(f"  本次未产生任何 commit，实例仍在原始版本。")
            log(f"  请人工审查后重试（修复后再跑会从当前版本继续）。")
            return 1

        # 每个迁移成功后提交版本与变更（由集成者最终 push；这里只 commit 形成可回滚历史点）
        # 注：按任务要求"全部成功后由集成者 commit"——这里不自动 commit，
        # 仅把改动留在工作区，多个迁移连续时下个 tag 仍可基于当前 HEAD。
        # 为让下一个迁移的回滚点正确，若还有后续迁移，需要一个提交锚点：
        # 我们用一个轻量提交，集成者可 squash/amend。
        if m is not pending[-1]:
            ar = git(instance, "add", "-A", check=False)
            cr = git(instance, "commit", "-m", f"substrate-migrate: {mid} ({m['from']}->{m['to']})", check=False)
            if ar.returncode != 0 or cr.returncode != 0:
                # 中间提交失败（缺 git 身份 / pre-commit hook 拒绝等）：绝不能继续——否则下个 tag 锚点错位，
                # 后续失败会回滚掉这个「已成功」的迁移且报告失真。回滚本迁移、停在上一个版本、转人工。
                emsg = ((cr.stderr or "") or (ar.stderr or "")).strip()
                log(f"  [ERROR] 中间提交失败（add rc={ar.returncode} commit rc={cr.returncode}）：{emsg}")
                git(instance, "reset", "--hard", tag, check=False)
                git(instance, "clean", "-fd", check=False)
                log(f"  已回滚 {mid} 到 {tag} 并中止。常见原因：未配置 git 身份 / pre-commit hook 失败——修复后重跑。")
                done = [x["id"] for x in pending[:pending.index(m)]]
                if done:
                    log(f"  注意：先前迁移 {done} 已成功并各自 commit，实例停在版本 {m['from']}。")
                return 1
            log(f"  中间提交（锚定下一迁移的回滚点；集成者可 squash）。")

    log(f"  ✅ 全部 {len(pending)} 个迁移成功。SUBSTRATE_VERSION 现为 {pending[-1]['to']}。")
    log(f"  改动留在工作区（最后一个迁移未自动 commit）。由集成者审查后 commit + push。")
    log(f"  多机协调: 其它机器 pull 到新版本后，再跑本 skill 会因版本闸门跳过（幂等）。")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
