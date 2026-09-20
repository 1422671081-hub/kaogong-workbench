# -*- coding: utf-8 -*-
import os as _os
_HOME = _os.environ.get("KG_HOME", _os.path.expanduser("~"))
def _p(*parts):
    return _os.path.join(_HOME, *parts)
"""批量解析 12 套卷 -> bank.json + meta.json（含 repair 清单）。OCR 缓存不在这跑。"""
import io
import json
import os
import re
import sys

sys.path.insert(0, _p("WorkBuddy", "2026-09-19-20-27-33", ".tmp", "gongkao"))
import fitz
from batch_lib import (PAPERS, QNO, FIG_STEM, CHART_STEM, fix, part_of, sub_of,
                       find_qidx, stack_save, crop, cache_paper)
import parse_zf5 as P

STATS = {}


def anchor_expl_end(rows, i_stem):
    """题号行之前、最近的 故正确答案/故本题选 行（材料图起点锚）"""
    for k in range(i_stem - 1, max(0, i_stem - 60), -1):
        if re.search(r"故正确答案|故本题选|综上", rows[k]["t"]):
            return rows[k]
    return rows[i_stem - 1] if i_stem else None


def parse_paper(cfg):
    frags = json.load(io.open(cfg["cache"], encoding="utf-8"))
    rows = P.merge_rows(frags)
    qidx, cand = find_qidx(rows, cfg["total"])
    got = {n for _, n in qidx}
    missing_no = [n for n in range(1, cfg["total"] + 1) if n not in got]
    result, repairs, meta = {}, [], {}
    for k, (i, qno) in enumerate(qidx):
        end = qidx[k + 1][0] if k + 1 < len(qidx) else len(rows)
        seg = rows[i:end]
        m0 = QNO.match(seg[0]["t"])
        first = m0.group(2).strip()
        run, j, real = P.grab_options(seg)
        if not run:
            nxt = None
            if k + 1 < len(qidx):
                nr = rows[qidx[k + 1][0]]
                nxt = {"p": nr["p"], "y0": nr["y0"]}
            repairs.append({"q": qno, "type": "no_opts",
                            "span": {"p": seg[0]["p"], "y0": seg[0]["y0"] - 4,
                                     "p1": (nxt["p"] if nxt else seg[-1]["p"]),
                                     "y1": (nxt["y0"] - 4 if nxt else seg[-1]["y1"])}})
            meta[qno] = {"stem_row": {"p": seg[0]["p"], "y0": seg[0]["y0"], "y1": seg[0]["y1"]}}
            continue
        s = next(n2 for n2, x in enumerate(seg) if x is run[0])
        stem = (first + "".join(x["t"] for x in seg[1:s])).strip()
        stem_end = seg[s - 1]["y0"] if s >= 1 else None
        groups = []
        for x in run:
            if P.OPT_X[0] <= x["x0"] <= P.OPT_X[1] and P.is_opt(x["t"]) is not None:
                groups.append({"first": x, "last": x, "rows": [x]})
                continue
            if groups:
                m = P.PROMO.match(x["t"])
                if m and x["x0"] <= P.OPT_X[1] + 3 and \
                        m.group(1).lower() == chr(ord(
                            next((c for c in P.OPT.match(groups[-1]["first"]["t"]).group(1).lower()
                                  if c in "abcd"), "?")) + 1):
                    groups.append({"first": x, "last": x, "rows": [x],
                                   "promo": m.group(2).strip() or m.group(1)})
                    continue
                groups[-1]["rows"].append(x)
                groups[-1]["last"] = x
        real_rows = [g["first"] for g in groups]
        start_letter = next((c for c in P.OPT.match(real_rows[0]["t"]).group(1).lower()
                             if c in "abcd"), "a")
        items = P.fill_missing(groups, stem_end, start_letter, qno, repairs)
        if any(g is None for g in items):
            repairs.append({"q": qno, "type": "missing_opt",
                            "letters": [ "ABCD"[n] for n, g in enumerate(items) if g is None ],
                            "span": {"p": real_rows[0]["p"],
                                     "y0": real_rows[0]["y0"],
                                     "y1": real_rows[-1]["y1"]}})
        letters, opts, red_pos = "ABCD", {}, None
        for n, g in enumerate(items):
            L = "ABCD"[n]
            if g is None:
                opts[L] = ""
                continue
            val = g.get("promo") if g.get("promo") is not None else P.is_opt(g["first"]["t"])
            if val is None:
                val = g["first"]["t"]
            if val == "" or (val and not re.search(r"[\u4e00-\u9fffA-Za-z0-9]", val)):
                val = "".join(x["t"] for x in g["rows"][1:])[:90] or "(见图)"
            opts[L] = val.strip()
            if any(x["red"] for x in g["rows"]) and red_pos is None:
                red_pos = n
        explain = "".join(x["t"] for x in seg[j:]) if j else ""
        src = None
        if red_pos is None:
            consumed = {id(x) for g in groups for x in g["rows"]}
            leftover = sorted((x for x in run if x["red"] and id(x) not in consumed),
                              key=lambda x: (x["p"], x["y0"]))
            if leftover:
                lr = leftover[0]
                idx = sum(1 for x in real_rows if (x["p"], x["y0"]) < (lr["p"], lr["y0"]))
                if idx < 4:
                    red_pos = idx
        if red_pos is None:
            m = P.ANS_SELF.search(explain)
            ans = next((g for g in m.groups() if g), "") if m else ""
            src = "文本自述"
        else:
            ans = "ABCD"[red_pos]; src = "红色标注"
        result[qno] = {"id": qno, "stem": stem, "options": opts, "answer": ans,
                       "answer_src": src, "explain": P.ANS_SELF.sub("", explain).strip(),
                       "page": seg[0]["p"] + 1}
        meta[qno] = {"stem_row": {"p": seg[0]["p"], "y0": seg[0]["y0"], "y1": seg[0]["y1"]},
                     "opt_first": real_rows[0] if real_rows else None,
                     "expl_start": ({"p": seg[j]["p"], "y0": seg[j]["y0"],
                                     "y1": seg[j]["y1"]} if j and j < len(seg) else None)}
    return rows, qidx, result, repairs, missing_no, meta


def build_bank(cfg, result, meta):
    bank = []
    for n in range(1, cfg["total"] + 1):
        r = result.get(n)
        if not r:
            continue
        part = part_of(cfg, n)
        stem = fix(r["stem"])
        q = {"pid": "%s-%d" % (cfg["paper"], n), "paper": cfg["paper"], "id": n,
             "part": part, "sub": sub_of(stem, r["options"]) if part == "判断推理" else "",
             "stem": stem, "options": {L: fix(v) for L, v in r["options"].items()},
             "answer": r["answer"], "explain": fix(r["explain"])}
        if q["sub"] == "图形推理":
            q["figimg"] = "zf2_%s_fig_%d.png" % (cfg["key"], n)      # 待批量生成
        bank.append(q)
    return bank


def main(only_cache=False):
    os.makedirs(os.path.join(os.path.dirname(list(PAPERS.values())[0]["cache"]), ".."), exist_ok=True)
    for key, cfg in PAPERS.items():
        print("==", key, cfg["paper"])
        if only_cache:
            cache_paper(cfg)
            continue
        rows, qidx, result, repairs, missing_no, meta = parse_paper(cfg)
        bank = build_bank(cfg, result, meta)
        with io.open(cfg["parsed"], "w", encoding="utf-8") as fp:
            json.dump({"result": result, "meta": meta, "repairs": repairs,
                       "missing_no": missing_no, "bank": bank}, fp, ensure_ascii=False, indent=1)
        n_ans = sum(1 for r in result.values() if r["answer"])
        dist = {}
        for r in result.values():
            dist[r["answer"]] = dist.get(r["answer"], 0) + 1
        miss_opt = sorted({r["q"] for r in repairs
                           if r.get("type") == "missing_opt" or "missing" in r})
        print("  解析 %d/%d | 缺题号 %s | 无答案 %d | 占位选项 %s"
              % (len(result), cfg["total"], missing_no or "无",
                 len(result) - n_ans, miss_opt or "无"))
        print("  分布", dist)
        STATS[key] = {"parsed": len(result), "total": cfg["total"],
                      "missing_no": missing_no, "dist": dist,
                      "miss_opt": miss_opt, "repairs": len(repairs)}
    with io.open(os.path.join(os.path.dirname(cfg["cache"]), "..", "batch_stats.json"),
                 "w", encoding="utf-8") as fp:
        json.dump(STATS, fp, ensure_ascii=False, indent=1)
    print("全部完成")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main(only_cache=(len(sys.argv) > 1 and sys.argv[1] == "cache"))
