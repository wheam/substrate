#!/usr/bin/env python3
"""substrate-collections — 给某收藏的行式 canonical(data.csv) 增/改一行 + 重算行数（零依赖）。

用法:
  # 增/改一行（按 id 去重幂等）。默认 dry-run，加 --apply 才写盘。
  python3 collections.py upsert --csv <path/to/data.csv> \
      --field id=ripgrep --field name=ripgrep --field category=cli [--field ...] [--apply]

  # 重算并打印某收藏的数据行数（与 substrate-doctor 同口径，杜绝计数漂移）。
  python3 collections.py count --csv <path/to/data.csv>

退出码: 0 = 成功; 2 = 调用错误（缺 --csv / 无 id / 路径不对等）。

设计约束（见引擎 docs/BUILD-PLAN.md §8 P5）:
  - python3 标准库零依赖（csv 模块），不假设 PyYAML。
  - 副作用默认 dry-run，--apply 才写。
  - CWD 无关：所有路径来自 --csv 参数。
  - 坏输入优雅退出不崩（缺文件、空 CSV、坏行、重复 id、含逗号/引号的值）。
  - **计数口径与 substrate-doctor/doctor.py 的 csv_rows() 完全一致**：
    数据行数 = max(非全空行数 - 1, 0)（减表头；忽略全空行）。
    upsert 与 count 都用这同一函数，保证写完后 doctor 不会报「计数漂移」。
"""
import sys, os
# 本脚本文件名为 collections.py，会遮蔽标准库的 `collections` 包。
# 直接 `python3 .../collections.py` 时，脚本所在目录在 sys.path[0]，
# 标准库（csv/argparse 经由 functools）`from collections import ...` 会误中本文件 → 循环导入崩溃。
# 先把脚本目录从 sys.path 摘掉，再导入标准库，杜绝该陷阱（与 CWD 无关）。
# 用 realpath（解析符号链接）：CPython 把 sys.path[0] 设成脚本目录的 realpath，
# 而 abspath 不解析符号链接——在 macOS /tmp→/private/tmp 这类符号链接路径下，
# abspath 比较会失配、摘不掉脚本目录，仍循环导入崩溃。realpath 两边对齐才稳。
_here = os.path.dirname(os.path.realpath(__file__))
sys.path[:] = [p for p in sys.path if os.path.realpath(p or ".") != _here]
import csv, argparse, tempfile


def read_csv(path):
    """读回 (header, rows)。文件不存在/空 → (None, [])。与 doctor 同样用 utf-8-sig 容忍 BOM。"""
    if not os.path.isfile(path):
        return None, []
    try:
        with open(path, newline="", encoding="utf-8-sig", errors="replace") as f:
            all_rows = list(csv.reader(f))
    except Exception as e:
        print(f"substrate-collections: 无法读取 {path}: {e}")
        return None, []
    if not all_rows:
        return None, []
    header = all_rows[0]
    body = all_rows[1:]
    return header, body


def data_row_count(header, body):
    """数据行数 = max(非全空行数 - 1, 0)，与 doctor.py csv_rows() 完全同口径。

    doctor 把表头与数据行一起算「非全空行」再减 1；这里复刻同一算法：
    把 header（若存在）与 body 合起来过滤全空行，再减表头。
    """
    rows = ([header] if header is not None else []) + list(body)
    non_empty = [r for r in rows if any((c or "").strip() for c in r)]
    return max(len(non_empty) - 1, 0)


def parse_fields(field_args):
    """--field k=v ... → (ordered_keys, dict)。重复 key 后者覆盖。"""
    keys, data = [], {}
    for raw in field_args or []:
        if "=" not in raw:
            return None, None, f"字段格式应为 key=value: {raw!r}"
        k, v = raw.split("=", 1)
        k = k.strip()
        if not k:
            return None, None, f"字段名为空: {raw!r}"
        if k not in data:
            keys.append(k)
        data[k] = v
    return keys, data, None


def cmd_count(args):
    header, body = read_csv(args.csv)
    if header is None and not body:
        if not os.path.isfile(args.csv):
            print(f"substrate-collections: 文件不存在: {args.csv}")
            return 2
        print(0)
        return 0
    print(data_row_count(header, body))
    return 0


def cmd_upsert(args):
    keys, data, perr = parse_fields(args.field)
    if perr:
        print(f"substrate-collections: {perr}")
        return 2
    if not data or not data.get("id", "").strip():
        print("substrate-collections: upsert 需要一个非空 --field id=<slug>（按 id 去重）")
        return 2
    new_id = data["id"].strip()
    data["id"] = new_id

    header, body = read_csv(args.csv)

    # 新建文件：表头 = id 在前 + 其余字段（去重保序）。
    if header is None:
        header = ["id"] + [k for k in keys if k != "id"]
        body = []
        is_new_file = True
    else:
        is_new_file = False
        # 既有文件但表头无 'id' 列：拒绝（不偷偷加列把旧行 id 留空），
        # 以守 doctor 的「每行有稳定 id」不变量；请用户先修表头。
        if "id" not in header:
            print(f"substrate-collections: {args.csv} 表头无 'id' 列，无法按 id 去重；请先修表头。")
            return 2
        # 出现新字段 → 作为新列补进表头（旧行该列留空）。
        for k in keys:
            if k not in header:
                header.append(k)

    id_idx = header.index("id")

    def row_to_record(row):
        rec = {header[i]: (row[i] if i < len(row) else "") for i in range(len(header))}
        if len(row) > len(header):
            rec["__overflow__"] = list(row[len(header):])   # 保留超宽（ragged）行的多余单元格，绝不静默丢弃
        return rec

    def record_to_row(rec):
        return [rec.get(col, "") for col in header] + list(rec.get("__overflow__", []))

    # 按 id 查现有行（去掉全空行；首个匹配为准，其余重复 id 告警）。
    matches = []
    kept = []
    for r in body:
        if not any((c or "").strip() for c in r):
            continue  # 丢弃全空行（不引入计数差）
        kept.append(r)
        rid = (r[id_idx] if id_idx < len(r) else "").strip()
        if rid == new_id:
            matches.append(len(kept) - 1)

    before_count = data_row_count(header, kept)

    if matches:
        # 改：合并到首个匹配行（保留旧值，只覆盖本次给的字段）→ 幂等。
        target = matches[0]
        rec = row_to_record(kept[target])
        for k in keys:
            rec[k] = data[k]
        rec["id"] = new_id
        kept[target] = record_to_row(rec)
        action = "改"
        dup_note = f"（注意：{len(matches)} 行同 id，只改第一行；建议清理重复）" if len(matches) > 1 else ""
    else:
        # 增：新行按表头列序填充。
        rec = {col: "" for col in header}
        for k in keys:
            rec[k] = data[k]
        rec["id"] = new_id
        kept.append(record_to_row(rec))
        action = "增"
        dup_note = ""

    after_count = data_row_count(header, kept)

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"substrate-collections upsert  csv={args.csv}  mode={mode}")
    print(f"  {action}行  id={new_id}  字段={', '.join(f'{k}={data[k]}' for k in keys)}{dup_note}")
    if is_new_file:
        print(f"  新建文件，表头: {','.join(header)}")
    print(f"  数据行数: {before_count} -> {after_count}")

    if not args.apply:
        print("  → dry-run，未写盘。确认无误后加 --apply。")
        print(f"  → 写盘后用 `count` 取权威行数并同步页面里的粗体计数（应为 {after_count}）。")
        return 0

    # 原子写：写临时文件再 rename，避免半截文件。lineterminator='\n' 保持 LF（不改写成 CRLF）。
    out = [header] + kept
    dest_dir = os.path.dirname(os.path.abspath(args.csv)) or "."
    tmp = None
    try:
        os.makedirs(dest_dir, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=dest_dir, suffix=".csv.tmp")
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
            csv.writer(f, lineterminator="\n").writerows(out)
        os.replace(tmp, args.csv)
    except Exception as e:
        if tmp and os.path.exists(tmp):        # 失败别把临时文件漏在（受 git 跟踪的）收藏目录里
            try: os.unlink(tmp)
            except OSError: pass
        print(f"substrate-collections: 写盘失败: {e}")
        return 2
    print(f"  → 已写 {args.csv}（{after_count} 数据行）。")
    print(f"  → 现在把索引页/分片页里的粗体计数同步为 **{after_count}** 条/rows，再跑 doctor。")
    return 0


def main(argv):
    ap = argparse.ArgumentParser(prog="collections.py", add_help=True)
    sub = ap.add_subparsers(dest="cmd")

    up = sub.add_parser("upsert", help="增/改一行（按 id 去重幂等）")
    up.add_argument("--csv", required=True, help="目标 data.csv 路径")
    up.add_argument("--field", action="append", metavar="key=value",
                    help="一对字段，可重复；必须含 id=<slug>")
    up.add_argument("--apply", action="store_true", help="真正写盘（默认 dry-run）")

    ct = sub.add_parser("count", help="重算并打印数据行数（与 doctor 同口径）")
    ct.add_argument("--csv", required=True, help="目标 data.csv 路径")

    if not argv:
        ap.print_help()
        return 2
    a = ap.parse_args(argv)
    if a.cmd == "upsert":
        return cmd_upsert(a)
    if a.cmd == "count":
        return cmd_count(a)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
