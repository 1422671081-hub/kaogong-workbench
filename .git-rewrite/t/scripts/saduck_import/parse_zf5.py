# -*- coding: utf-8 -*-
import os as _os
_HOME = _os.environ.get("KG_HOME", _os.path.expanduser("~"))
def _p(*parts):
    return _os.path.join(_HOME, *parts)
"""SaDuck 版解析器 v5.1

在 v5 基础上修三处：
  - 「5C.」双字符前缀：取其中的 A-D 字母（题12）
  - 题干与选项间的正常空行不再误判为缺行（题61）
  - 「A.」纯字母锚点行（表格选项题）按锚点吸收后续表格行；行距倍数
    只认 2 倍附近且小于 3.2 倍，跨页/表格大间距不插占位（题86）
"""
import io
import json
import re
import statistics
import sys

CACHE = _p("WorkBuddy", "2026-09-19-20-27-33", ".tmp", "gongkao", "zf_lines.json")
REPAIR = _p("WorkBuddy", "2026-09-19-20-27-33", ".tmp", "gongkao", "zf_repair.json")
OUT = _p("WorkBuddy", "2026-09-19-20-27-33", ".tmp", "gongkao", "zf_parsed.json")
TOTAL = 130
PAGE_H = 842.0
SP = 24.0            # 选项行距基准

QNO = re.compile(r"^\s*(\d{1,3})\s*[^\d\u4e00-\u9fff]{0,3}\s*(\S.*)$")
OPT = re.compile(r"^\s*([A-Za-z0-9@OGQo]{1,2})\s*([.、．…·]?)\s*(\S.*)$")
PROMO = re.compile(r"^[^\u4e00-\u9fff]{0,2}\s*([A-Da-d])\s*[.、．…·]\s*(\S*)\s*$")
ANS_SELF = re.compile(r"故正确答案\s*为\s*([A-D])|故本题选\s*([A-D])|正确答案\s*是\s*([A-D])")
EXPL_HEAD = re.compile(r"^(本题|第[一二三]|根据|故|解析|横线|对比|综上|步骤|[A-D]项|综上)")
NOISE = [
    re.compile(r"SaDuck", re.I), re.compile(r"历年试卷"),
    re.compile(r"saduck\.top", re.I), re.compile(r"^\s*\d{4}\s*/\s*\d{1,2}\s*/\s*\d{1,2}"),
    re.compile(r"^\s*\d+\s*/\s*\d+\s*$"), re.compile(r"^\s*\d{1,5}\s*$"),
]
QNO_X, OPT_X = 46.5, (46.0, 60.0)
Y_MERGE = 6.0

# OCR 整行丢失、经人工看图确认后回填的行
INJECT = [
    {"p": 55, "y0": 352.0, "y1": 372.0, "x0": 39.8, "t": "92. 载歌:载舞", "red": False},
]


def is_opt(t):
    """返回选项正文（空串=纯字母锚点行）；不是选项行返回 None"""
    m = OPT.match(t)
    if not m:
        return None
    pre, sep, rest = m.group(1), m.group(2), m.group(3).strip()
    if len(pre) == 2:
        letter = next((c for c in pre if c.lower() in "abcd"), None)
        if letter is None:
            return None
        pre = letter
    is_abcd = pre.lower() in "abcd"
    if sep:
        return rest
    if not is_abcd:
        return None
    if rest and re.match(r"^[\u4e00-\u9fff]", rest) and EXPL_HEAD.match(pre + rest[0]):
        return None                        # 「A项错误」这类解析行
    return rest


def merge_rows(frags):
    frags = sorted(frags, key=lambda f: (f["p"], f["y0"], f["x0"]))
    groups, cur = [], []
    for f in frags:
        if cur and f["p"] == cur[0]["p"] and abs(f["y0"] - cur[0]["y0"]) <= Y_MERGE:
            cur.append(f)
        else:
            if cur:
                groups.append(cur)
            cur = [f]
    if cur:
        groups.append(cur)
    out = []
    for g in groups:
        g = sorted(g, key=lambda f: f["x0"])
        buf = g[0]["t"]
        for nxt in g[1:]:
            a, b = buf[-1:], nxt["t"][:1]
            sep = " " if (a.isascii() and a.isalnum() and b.isascii() and b.isalnum()) else ""
            buf += sep + nxt["t"]
        row = {"p": g[0]["p"], "y0": min(x["y0"] for x in g), "y1": max(x["y1"] for x in g),
               "x0": min(x["x0"] for x in g), "t": re.sub(r"\s+", " ", buf).strip(),
               "red": any(x["red"] for x in g)}
        if (row["y0"] > PAGE_H - 42 or row["y0"] < 40) and any(p.search(row["t"]) for p in NOISE):
            continue
        out.append(row)
    out.sort(key=lambda r: (r["p"], r["y0"]))
    return out


def find_qidx(rows):
    cand = []
    for i, r in enumerate(rows):
        m = QNO.match(r["t"])
        if not m:
            continue
        n = int(m.group(1))
        if 1 <= n <= TOTAL and r["x0"] <= QNO_X and len(m.group(2)) >= 4:
            cand.append((i, n))
    picked, target, k = [], 1, 0
    while k < len(cand) and target <= TOTAL:
        i, n = cand[k]
        if n == target:
            picked.append((i, n)); target += 1; k += 1
        elif target < n <= target + 2:
            target = n; picked.append((i, n)); target += 1; k += 1
        else:
            k += 1
    have = {n for _, n in picked}
    used = {i for i, _ in picked}
    for t in range(1, TOTAL + 1):
        if t in have:
            continue
        for i, n in cand:
            if n == t and i not in used:
                picked.append((i, n)); used.add(i); break
    picked.sort()
    return picked, cand


def build_run(seg, s):
    run, j, real = [seg[s]], s + 1, 1
    while j < len(seg) and real < 4:
        r = seg[j]
        if OPT_X[0] <= r["x0"] <= OPT_X[1] and is_opt(r["t"]) is not None:
            run.append(r); real += 1; j += 1
            continue
        gap = r["y0"] - run[-1]["y0"]
        if (run[-1]["p"] == r["p"] and 0 <= gap < 40) or \
           (r["p"] > run[-1]["p"] and r["y0"] < 140):
            if EXPL_HEAD.match(r["t"]):
                break
            run.append(r); j += 1
            continue
        break
    return run, j, real


def grab_options(seg):
    tries = []
    for s in range(1, min(len(seg), 25)):
        r = seg[s]
        if not (OPT_X[0] <= r["x0"] <= OPT_X[1]):
            continue
        m = OPT.match(r["t"])
        if not m:
            continue
        pre = m.group(1).lower()
        if len(pre) == 2:
            pre = next((c for c in pre if c.lower() in "abcd"), "?")
        if pre[0] in "abcd":
            tries.append((pre[0], s))
    for start_letter in "abc":
        for s in [s for L, s in tries if L == start_letter]:
            run, j, real = build_run(seg, s)
            if real >= {"a": 3, "b": 2, "c": 2}[start_letter]:
                return run, j, real
    return [], None, 0


def fill_missing(groups, stem_end, start_letter, qno, repairs):
    """groups: [{first,last,rows}] 选项组（含续行）。按组间距倍数补占位符。"""
    gaps = [g2["first"]["y0"] - g1["last"]["y0"]
            for g1, g2 in zip(groups, groups[1:])]
    near = [g for g in gaps if 15 <= g <= 35]        # 正常行距附近的间隙
    sp = statistics.median(near) if near else SP
    lead = "abcd".index(start_letter)                # 首选项不是 A：前面必有缺行
    items = [None] * lead + [groups[0]]
    if lead == 0 and stem_end is not None:
        g0 = groups[0]["first"]["y0"] - stem_end
        if 1.9 * sp <= g0 < 2.6 * sp:
            items.insert(0, None)
    for g1, g2 in zip(groups, groups[1:]):
        g = g2["first"]["y0"] - g1["last"]["y0"]
        if 1.8 * sp <= g < 2.6 * sp:
            items.append(None)
        items.append(g2)
    ins = sum(1 for x in items if x is None)
    if ins:
        repairs.append({"q": qno, "missing": ins,
                        "rows": [{"p": g["first"]["p"], "y0": g["first"]["y0"]}
                                 for g in groups]})
    return items[:4]


def main():
    frags = json.load(io.open(CACHE, encoding="utf-8")) + INJECT
    rows = merge_rows(frags)
    qidx, cand = find_qidx(rows)
    got = [n for _, n in qidx]
    print("视觉行 %d | 题号候选 %d -> 命中 %d | 缺号: %s" % (
        len(rows), len(cand), len(qidx),
        [n for n in range(1, TOTAL + 1) if n not in got] or "无"))

    result, problems, repairs = {}, [], []
    for k, (i, qno) in enumerate(qidx):
        end = qidx[k + 1][0] if k + 1 < len(qidx) else len(rows)
        seg = rows[i:end]
        first = QNO.match(seg[0]["t"]).group(2).strip()
        run, j, real = grab_options(seg)
        if not run:
            problems.append((qno, "未找到选项族"))
            continue
        s = next(n for n, x in enumerate(seg) if x is run[0])
        stem = (first + "".join(x["t"] for x in seg[1:s])).strip()
        stem_end = seg[s - 1]["y0"] if s >= 1 else None

        # 选项组：真实选项行 + 其吸收的续行；被 OCR 弄脏的选项行（如「<C. C」）
        # 若字母正好接续上一个选项，则提升为独立选项组
        groups = []

        def prev_letter():
            if not groups:
                return "?"
            pre = OPT.match(groups[-1]["first"]["t"]).group(1).lower()
            return next((c for c in pre if c in "abcd"), "?")

        for x in run:
            if OPT_X[0] <= x["x0"] <= OPT_X[1] and is_opt(x["t"]) is not None:
                groups.append({"first": x, "last": x, "rows": [x]})
                continue
            if groups:
                m = PROMO.match(x["t"])
                if m and x["x0"] <= OPT_X[1] + 3 and \
                        m.group(1).lower() == chr(ord(prev_letter()) + 1):
                    groups.append({"first": x, "last": x, "rows": [x],
                                   "promo": m.group(2).strip() or m.group(1)})
                    continue
                groups[-1]["rows"].append(x)
                groups[-1]["last"] = x
        real_rows = [g["first"] for g in groups]
        start_letter = next((c for c in OPT.match(real_rows[0]["t"]).group(1).lower()
                             if c in "abcd"), "a")
        items = fill_missing(groups, stem_end, start_letter, qno, repairs)

        letters, opts, red_pos = "ABCD", {}, None
        for n, g in enumerate(items):
            L = letters[n]
            if g is None:
                opts[L] = ""                  # 占位：待修补
                continue
            row = g["first"]
            if g.get("promo") is not None:
                val = g["promo"]
            else:
                val = is_opt(row["t"])
                if val is None:
                    val = row["t"]
                if val and not re.search(r"[\u4e00-\u9fffA-Za-z0-9]", val):
                    val = ""                  # 「A. .」这类纯标点也按锚点处理
                if val == "":                 # 「A.」锚点：吸收组内后续行（表格题）
                    val = "".join(x["t"] for x in g["rows"][1:])[:90]
            opts[L] = val.strip()
            if any(x["red"] for x in g["rows"]) and red_pos is None:
                red_pos = n
        explain = "".join(x["t"] for x in seg[j:]) if j else ""
        src = None
        if red_pos is None:
            # 被占位的那一行可能恰是红标答案行（如题68「人50」）——用未被吸收的红行定位
            consumed = {id(x) for x in real_rows}
            leftover = sorted((x for x in run if x["red"] and id(x) not in consumed),
                              key=lambda x: (x["p"], x["y0"]))
            if leftover:
                lr = leftover[0]
                idx = sum(1 for x in real_rows if (x["p"], x["y0"]) < (lr["p"], lr["y0"]))
                if idx < 4:
                    red_pos = idx
        if red_pos is None:
            m = ANS_SELF.search(explain)
            ans = next((g for g in m.groups() if g), "") if m else ""
            src = "文本自述"
        else:
            ans = letters[red_pos]; src = "红色标注"
        result[qno] = {"id": qno, "stem": stem, "options": opts, "answer": ans,
                       "answer_src": src, "explain": ANS_SELF.sub("", explain).strip(),
                       "page": seg[0]["p"] + 1}

    red_n = sum(1 for v in result.values() if v["answer_src"] == "红色标注")
    no_ans = [n for n, v in result.items() if not v["answer"]]
    no_opt = [n for n, v in result.items() if len([x for x in "ABCD" if v["options"].get(x)]) < 4]
    print("成功 %d/%d | 红色 %d | 无答案 %s | 选项不全 %s" % (
        len(result), TOTAL, red_n, no_ans or "无", no_opt or "无"))
    if problems:
        print("结构失败:", [p[0] for p in problems])
    print("需补行 %d 处:" % len(repairs), [(r["q"], r["missing"]) for r in repairs])

    with io.open(OUT, "w", encoding="utf-8") as fp:
        json.dump(result, fp, ensure_ascii=False, indent=1)
    with io.open(REPAIR, "w", encoding="utf-8") as fp:
        json.dump(repairs, fp, ensure_ascii=False, indent=1)
    print("已写出", OUT)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
