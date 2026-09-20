# -*- coding: utf-8 -*-
import os as _os
_HOME = _os.environ.get("KG_HOME", _os.path.expanduser("~"))
def _p(*parts):
    return _os.path.join(_HOME, *parts)
"""2018 国考副省级（文字层版式）解析器：dict 按 y 重建行流 -> 切题/选项/解析。"""
import io
import json
import os
import re
import sys

import fitz

PDF = _p("Desktop", "行测真题pdf", "2018年国家《行测》题（副省级）-全部题目-常规.pdf")
OUT = _p("WorkBuddy", "2026-09-19-20-27-33", ".tmp", "gongkao", "p2018_parsed.json")
TOTAL = 135

QNO = re.compile(r"^(\d{1,3})\s*[.、．]?\s*(\S.*)$")
OPT = re.compile(r"^([A-D])[.、]\s*(\S.*)$")
ANS = re.compile(r"【答案】\s*([A-D])")
SECTION = re.compile(r"^[一二三四五六七八九十]+、")


def build_lines(doc):
    out = []
    for pno in range(doc.page_count):
        d = doc[pno].get_text("dict")
        for b in d.get("blocks", []):
            if b.get("type") != 0:
                continue
            for l in b.get("lines", []):
                t = "".join(s.get("text", "") for s in l.get("spans", "")).strip()
                if not t:
                    continue
                x0, y0, x1, y1 = l["bbox"]
                out.append({"p": pno, "y0": round(y0, 1), "x0": round(x0, 1), "t": t})
    out.sort(key=lambda r: (r["p"], r["y0"], r["x0"]))
    # 同一视觉行合并（题号「1.」与题干、选项「A.」与内容是独立 line）
    res, cur = [], []
    for r in out:
        if cur and r["p"] == cur[0]["p"] and abs(r["y0"] - cur[0]["y0"]) <= 3:
            cur.append(r)
        else:
            if cur:
                res.append(cur)
            cur = [r]
    if cur:
        res.append(cur)
    rows = []
    for g in res:
        g.sort(key=lambda r: r["x0"])
        t = g[0]["t"]
        for nxt in g[1:]:
            sep = " " if (t[-1:].isascii() and t[-1:].isalnum() and nxt["t"][:1].isascii()) else ""
            t += sep + nxt["t"]
        rows.append({"p": g[0]["p"], "y0": g[0]["y0"], "x0": g[0]["x0"],
                     "t": re.sub(r"\s+", " ", t).strip()})
    # 过滤页眉/页码
    out2 = []
    for r in rows:
        t = r["t"]
        if t.startswith("2018年国家《行测》题"):
            continue
        if re.fullmatch(r"\d{1,2}", t) and r["x0"] > 500:
            continue
        out2.append(r)
    return out2


def main():
    doc = fitz.open(PDF)
    lines = build_lines(doc)
    doc.close()
    print("有效行", len(lines))

    # 解析区起点：第一个「【答案】」行
    ans_start = next((k for k, r in enumerate(lines) if "【答案】" in r["t"]), None)
    if ans_start is None:
        raise SystemExit("找不到解析区")
    print("解析区起点: p%d y%.0f「%s」" % (lines[ans_start]["p"], lines[ans_start]["y0"], lines[ans_start]["t"][:30]))

    # ---- 题目区 ----
    result = {}
    cur, stem_parts, opts, cur_opt = None, [], {}, None
    section = ""
    for r in lines[:ans_start]:
        t = r["t"]
        if SECTION.match(t):
            section = t
            continue
        if t.startswith("根据题目要求"):
            continue
        m = QNO.match(t)
        mo = OPT.match(t)
        if m and int(m.group(1)) == (cur or 0) + 1 and r["x0"] < 60:
            if cur:
                result[cur] = {"stem": "".join(stem_parts).strip(), "options": opts, "section": section}
            cur = int(m.group(1)); stem_parts = [m.group(2)]; opts = {}; cur_opt = None
            continue
        if mo and cur:
            cur_opt = mo.group(1)
            opts[cur_opt] = mo.group(2).strip()
            continue
        if cur:
            if cur_opt and opts.get(cur_opt) is not None and not stem_parts[-1:] == [None]:
                opts[cur_opt] = (opts[cur_opt] + t).strip()
            else:
                stem_parts.append(t)
    if cur:
        result[cur] = {"stem": "".join(stem_parts).strip(), "options": opts, "section": section}
    print("题目区解析", len(result), "题")

    # ---- 解析区 ----
    expl, ans_map, cur_no = {}, {}, None
    for r in lines[ans_start:]:
        t = r["t"]
        m = QNO.match(t)
        ma = ANS.search(t)
        if m and int(m.group(1)) == (cur_no or 0) + 1 and r["x0"] < 60 and len(t) < 12:
            cur_no = int(m.group(1))          # 解析区题号骨架行（如「8. 9. 10.」组不匹配，见下）
            ma2 = ANS.search(t)
            if ma2:                            # 题号与【答案】同行（如「1.【答案】 D」）
                ans_map[cur_no] = ma2.group(1)
            continue
        if ma:
            cur_no = cur_no or 0
            # 【答案】行的题号需要靠顺序推进：从 1 开始
            nxt = cur_no + 1 if cur_no else 1
            # 兜底：若已有解析且隔题，跳号对齐
            expl.setdefault(nxt, [])
            ans_map[nxt] = ma.group(1)
            cur_no = nxt
            continue
        if cur_no:
            expl.setdefault(cur_no, []).append(t)

    # ---- 组装 ----
    for n in range(1, TOTAL + 1):
        q = result.get(n, {})
        answer = ans_map.get(n, "")
        ex = "".join(expl.get(n, []))
        ex = re.sub(r"^考点[：:]", "", ex).strip()
        result[n] = {"id": n, "stem": q.get("stem", ""), "options": q.get("options", {}),
                     "answer": answer, "explain": ex, "section": q.get("section", "")}
    with io.open(OUT, "w", encoding="utf-8") as fp:
        json.dump(result, fp, ensure_ascii=False, indent=1)
    got = [n for n in range(1, TOTAL + 1) if result[n]["stem"]]
    dist = {}
    for n in got:
        a = result[n]["answer"]
        dist[a] = dist.get(a, 0) + 1
    print("完成 %d/%d 题 | 答案分布 %s" % (len(got), TOTAL, dist))
    for n in (1, 2, 61, 116):
        r = result[n]
        print("--- %d [%s] ans=%s" % (n, r["section"][:12], r["answer"]))
        print("  题干:", r["stem"][:46])
        for L in "ABCD":
            print("   %s. %s" % (L, r["options"].get(L, "(缺)")[:36]))
        print("  解析:", r["explain"][:40])


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
