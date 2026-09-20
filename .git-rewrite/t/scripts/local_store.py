#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""考公题库 · 本地模式数据管理（无 WorkBuddy 环境用）

数据全部落在本地目录，纯标准库、零第三方依赖。

    python3 local_store.py init    --dir ./kaogong-data
    python3 local_store.py add-q   --dir ./kaogong-data --json new-questions.json
    python3 local_store.py wrong   --dir ./kaogong-data --pid "2022国考副省级-76"
    python3 local_store.py due     --dir ./kaogong-data
    python3 local_store.py checkin --dir ./kaogong-data --module 言语理解 --done 10 --correct 8 --minutes 15
    python3 local_store.py stats   --dir ./kaogong-data
    python3 local_store.py build   --dir ./kaogong-data --out ./考公工作台.html

数据文件：
    questions.json  题目数组（一题一个对象）
    wrong.json      错题状态  { pid: {times,stage,next,lastAt,note} }
    checkin.json    打卡记录  { "YYYY-MM-DD": { modules:{名:{done,correct,minutes}}, note } }
    img/            配图目录（build 时按需 base64 内嵌）
"""
import argparse
import base64
import datetime
import io
import json
import os
import re
import sys

EBBING = [1, 2, 4, 7, 15, 30]          # 艾宾浩斯间隔（天）
GRADUATED = 99                          # 复习阶段到 99 视为毕业
MODULES = ["常识判断", "言语理解", "数量关系", "判断推理", "资料分析"]
CHECKIN_MODULES = ["言语理解", "逻辑判断", "数量关系", "资料分析",
                   "政治理论", "常识判断", "申论", "综合运用"]

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(os.path.dirname(HERE), "assets", "template.html")


# ---------------- 基础设施 ----------------
def jload(path, default):
    if not os.path.exists(path):
        return default
    try:
        with io.open(path, encoding="utf-8") as fp:
            return json.load(fp)
    except Exception as e:
        sys.stderr.write("读取 %s 失败：%s\n" % (path, e))
        return default


def jdump(path, obj):
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as fp:
        json.dump(obj, fp, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def today():
    return datetime.date.today().isoformat()


def add_days(date_str, n):
    d = datetime.date.fromisoformat(date_str[:10])
    return (d + datetime.timedelta(days=n)).isoformat()


def paths(d):
    return {
        "root": d,
        "q": os.path.join(d, "questions.json"),
        "w": os.path.join(d, "wrong.json"),
        "c": os.path.join(d, "checkin.json"),
        "img": os.path.join(d, "img"),
    }


# ---------------- 子命令 ----------------
def cmd_init(a):
    p = paths(a.dir)
    os.makedirs(p["img"], exist_ok=True)
    for key in ("q", "w", "c"):
        if not os.path.exists(p[key]):
            jdump(p[key], [] if key == "q" else {})
    print("已初始化数据目录:", os.path.abspath(a.dir))
    print("  questions.json / wrong.json / checkin.json / img/")


def cmd_add_q(a):
    p = paths(a.dir)
    if not os.path.exists(p["q"]):
        cmd_init(a)
    bank = jload(p["q"], [])
    with io.open(a.json, encoding="utf-8") as fp:
        new = json.load(fp)
    if isinstance(new, dict):
        new = new.get("questions") or new.get("records") or [new]
    if not isinstance(new, list):
        raise SystemExit("--json 文件必须是数组，或是含 questions 数组的对象")

    have = {q.get("pid") for q in bank}
    added, replaced, skipped = 0, 0, 0
    for q in new:
        pid = q.get("pid")
        if not pid:
            bid = q.get("paper", "未命名") + "-" + str(q.get("id", "?"))
            q["pid"] = bid
            pid = bid
        if pid in have:
            for i, old in enumerate(bank):
                if old.get("pid") == pid:
                    bank[i] = q
                    replaced += 1
                    break
        else:
            bank.append(q)
            have.add(pid)
            added += 1
    bank.sort(key=lambda x: (x.get("paper", ""), x.get("id") or 0))
    jdump(p["q"], bank)

    # 缺图登记
    missing = []
    for q in new:
        for f in [q.get("img"), q.get("qimg")] + list(q.get("imgs") or []):
            if f and not os.path.exists(os.path.join(p["img"], f)):
                missing.append(f)

    print("新增 %d 题，覆盖 %d 题，题库现有 %d 题" % (added, replaced, len(bank)))
    if missing:
        print("提示：以下配图还没放进 img/，build 时会被跳过：")
        for f in sorted(set(missing)):
            print("   ", f)


def cmd_wrong(a):
    p = paths(a.dir)
    w = jload(p["w"], {})
    t = a.today or today()
    rec = w.get(a.pid) or {"times": 0, "stage": 0, "next": None}
    rec["times"] = int(rec.get("times", 0)) + 1
    rec["stage"] = 0
    rec["next"] = add_days(t, EBBING[0])
    rec["lastAt"] = t
    if a.note:
        rec["note"] = a.note
    w[a.pid] = rec
    jdump(p["w"], w)
    print("已记错题 %s：累计 %d 次，下次复习 %s" % (a.pid, rec["times"], rec["next"]))


def cmd_due(a):
    p = paths(a.dir)
    w = jload(p["w"], {})
    bank = {q.get("pid"): q for q in jload(p["q"], [])}
    t = a.today or today()
    rows = []
    for pid, r in w.items():
        if r.get("stage", 0) >= GRADUATED:
            continue
        nxt = r.get("next")
        if nxt and nxt[:10] <= t:
            q = bank.get(pid) or {}
            rows.append((r.get("stage", 0), pid, q.get("part", ""),
                         (q.get("stem") or "")[:24], nxt, r.get("times", 0)))
    rows.sort()
    if not rows:
        print("今天没有待复习的题。")
        return
    print("今日待复习 %d 题（%s）\n" % (len(rows), t))
    print("%-4s %-22s %-8s %-6s %-12s %s" % ("轮次", "pid", "模块", "错次", "下次复习", "题干"))
    for stage, pid, part, stem, nxt, times in rows:
        print("%-6d %-22s %-8s %-6d %-12s %s" % (stage, pid, part, times, nxt, stem))


def cmd_review(a):
    """报告复习结果，推进或打回"""
    p = paths(a.dir)
    w = jload(p["w"], {})
    rec = w.get(a.pid)
    if not rec:
        raise SystemExit("错题本里没有 %s" % a.pid)
    t = a.today or today()
    if a.right:
        rec["stage"] = int(rec.get("stage", 0)) + 1
        if rec["stage"] >= len(EBBING):
            rec["stage"] = GRADUATED
            rec["next"] = None
            print("%s 已完成全部 6 轮复习，毕业 ✓" % a.pid)
        else:
            rec["next"] = add_days(t, EBBING[rec["stage"]])
            print("%s 推进到第 %d 轮，下次复习 %s" % (a.pid, rec["stage"], rec["next"]))
    else:
        rec["stage"] = 0
        rec["next"] = add_days(t, EBBING[0])
        print("%s 复习又错，打回第 1 轮，明天再见" % a.pid)
    w[a.pid] = rec
    jdump(p["w"], w)


def cmd_checkin(a):
    p = paths(a.dir)
    c = jload(p["c"], {})
    d = a.date or today()
    day = c.setdefault(d, {"modules": {}, "note": ""})
    if a.clear:
        c.pop(d, None)
        jdump(p["c"], c)
        print("已清空 %s 的打卡记录" % d)
        return
    done, correct, minutes = a.done or 0, a.correct or 0, a.minutes or 0
    if correct > done:
        raise SystemExit("正确数不能大于题数")
    mod = day["modules"].get(a.module) or {"done": 0, "correct": 0, "minutes": 0}
    mod["done"] += done
    mod["correct"] += correct
    mod["minutes"] += minutes
    day["modules"][a.module] = mod
    if a.note:
        day["note"] = a.note
    if sum(m["done"] for m in day["modules"].values()) == 0:
        c.pop(d, None)
    jdump(p["c"], c)
    tot = sum(m["done"] for m in day["modules"].values())
    print("已记 %s 的打卡：%s +%d 题（当日共 %d 题）" % (d, a.module, done, tot))


def cmd_stats(a):
    p = paths(a.dir)
    c = jload(p["c"], {})
    if not c:
        print("还没有打卡记录。")
        return
    print("%-12s %-6s %-6s %-8s %s" % ("日期", "题量", "正确", "正确率", "时长(分)"))
    td = tc = tm = 0
    for d in sorted(c.keys(), reverse=True):
        mods = c[d].get("modules", {})
        dd = sum(m["done"] for m in mods.values())
        cc = sum(m["correct"] for m in mods.values())
        mm = sum(m["minutes"] for m in mods.values())
        td += dd
        tc += cc
        tm += mm
        rate = ("%d%%" % round(cc * 100.0 / dd)) if dd else "-"
        print("%-12s %-6d %-6d %-8s %d" % (d, dd, cc, rate, mm))
    print("-" * 46)
    print("合计 %d 题 / 正确 %d / 正确率 %s / 累计 %d 分钟" % (
        td, tc, ("%d%%" % round(tc * 100.0 / td)) if td else "-", tm))

    w = jload(p["w"], {})
    active = [k for k, v in w.items() if v.get("stage", 0) < GRADUATED]
    print("错题本：%d 题在册（其中 %d 题未毕业）" % (len(w), len(active)))


def cmd_build(a):
    p = paths(a.dir)
    if not os.path.exists(TEMPLATE):
        raise SystemExit("找不到模板文件：%s" % TEMPLATE)
    bank = jload(p["q"], [])
    if not bank:
        raise SystemExit("题库是空的，先 add-q 录题")

    # 图片 -> base64
    img_data = {}
    missing = []
    for q in bank:
        for f in [q.get("img"), q.get("qimg")] + list(q.get("imgs") or []):
            if not f or f in img_data:
                continue
            fp = os.path.join(p["img"], f)
            if not os.path.exists(fp):
                missing.append(f)
                continue
            ext = os.path.splitext(f)[1].lower().lstrip(".") or "png"
            mime = "jpeg" if ext in ("jpg", "jpeg") else ext
            with open(fp, "rb") as fh:
                img_data[f] = "data:image/%s;base64,%s" % (
                    mime, base64.b64encode(fh.read()).decode("ascii"))

    tpl = io.open(TEMPLATE, encoding="utf-8").read()
    import hashlib
    ver = hashlib.md5(json.dumps(img_data, sort_keys=True).encode()).hexdigest()[:8] if img_data else "0"

    html = tpl.replace("/*__BANK_JSON__*/", json.dumps(bank, ensure_ascii=False))
    html = html.replace("/*__IMG_DATA_JSON__*/", json.dumps(img_data, ensure_ascii=False))
    html = html.replace("/*__IMG_VER__*/", ver)

    out = a.out or os.path.join(p["root"], "考公工作台.html")
    with io.open(out, "w", encoding="utf-8", newline="") as fp:
        fp.write(html)

    print("已生成单文件刷题页:", os.path.abspath(out))
    print("  题目 %d 题 | 内嵌图片 %d 张 | 文件 %.1f KB" % (
        len(bank), len(img_data), os.path.getsize(out) / 1024.0))
    print("  双击即可打开，图片已内嵌，不用带 img/ 目录")
    if missing:
        print("  警告：%d 张配图缺失，页面里会显示占位提示：" % len(set(missing)))
        for f in sorted(set(missing)):
            print("     ", f)


def main():
    ap = argparse.ArgumentParser(description="考公题库 · 本地模式")
    sub = ap.add_subparsers(dest="cmd")

    def add(name, fn, **kw):
        s = sub.add_parser(name, **kw)
        s.add_argument("--dir", default="./kaogong-data")
        s.set_defaults(func=fn)
        return s

    add("init", cmd_init, help="初始化数据目录")
    s = add("add-q", cmd_add_q, help="录入题目（JSON 文件）")
    s.add_argument("--json", required=True)
    s = add("wrong", cmd_wrong, help="记一道错题")
    s.add_argument("--pid", required=True)
    s.add_argument("--note", default="")
    s.add_argument("--today", default="")
    s = add("due", cmd_due, help="列出今日待复习")
    s.add_argument("--today", default="")
    s = add("review", cmd_review, help="报告复习结果")
    s.add_argument("--pid", required=True)
    s.add_argument("--right", action="store_true", help="答对则推进一轮")
    s.add_argument("--today", default="")
    s = add("checkin", cmd_checkin, help="记打卡")
    s.add_argument("--module", default="")
    s.add_argument("--done", type=int, default=0)
    s.add_argument("--correct", type=int, default=0)
    s.add_argument("--minutes", type=int, default=0)
    s.add_argument("--date", default="")
    s.add_argument("--note", default="")
    s.add_argument("--clear", action="store_true", help="清空该日打卡")
    add("stats", cmd_stats, help="统计概览")
    s = add("build", cmd_build, help="生成单文件刷题页")
    s.add_argument("--out", default="")

    args = ap.parse_args()
    if not getattr(args, "func", None):
        ap.print_help()
        sys.exit(1)
    if getattr(args, "cmd", "") in ("checkin",) and not args.module and not args.clear:
        raise SystemExit("checkin 需要 --module（可用模块：%s）" % " / ".join(CHECKIN_MODULES))
    args.func(args)


if __name__ == "__main__":
    main()
