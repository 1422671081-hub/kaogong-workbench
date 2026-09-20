# -*- coding: utf-8 -*-
import os as _os
_HOME = _os.environ.get("KG_HOME", _os.path.expanduser("~"))
def _p(*parts):
    return _os.path.join(_HOME, *parts)
"""missing_opt 题裁选项区图兜底；渲染 no_opts/缺号/无答案条带图供人工修补。"""
import io
import json
import os
import re
import sys

sys.path.insert(0, _p("WorkBuddy", "2026-09-19-20-27-33", ".tmp", "gongkao"))
import fitz
from PIL import Image
from batch_lib import PAPERS, IMGDIR, crop, stack_save

RENDER = _p("WorkBuddy", "2026-09-19-20-27-33", ".tmp", "gongkao", "zf")


def span_parts(p0, y_lo, p1, y_hi):
    if p0 == p1:
        return [(p0, y_lo, y_hi)] if y_hi - y_lo >= 8 else []
    parts = [(p0, y_lo, 806)]
    for p in range(p0 + 1, p1):
        parts.append((p, 44, 806))
    if y_hi - 44 >= 8:
        parts.append((p1, 44, y_hi))
    return parts


def main():
    doc_cache = {}
    jobs = []          # (label, p0, y_lo, p1, y_hi)
    todo = []
    for key, cfg in PAPERS.items():
        d = json.load(io.open(cfg["parsed"], encoding="utf-8"))
        bank = {q["id"]: q for q in d["bank"]}
        # ---- missing_opt：选项区图兜底 ----
        for r in d["repairs"]:
            if r.get("type") != "missing_opt":
                continue
            q = bank.get(r["q"])
            sp = r.get("span") or {}
            if not q or "p" not in sp:
                continue
            fn = "zf2_%s_opt_%d.png" % (key, r["q"])
            doc_cache.setdefault(key, fitz.open(cfg["pdf"]))
            ims = [crop(doc_cache[key], sp["p"], sp["y0"] - 10, sp["y1"] + 10)]
            if stack_save(ims, os.path.join(IMGDIR, fn)):
                q.setdefault("imgs", []).append(fn)
                for L in "ABCD":
                    if not q["options"].get(L):
                        q["options"][L] = "(见图)"
                print("%s 题%d 选项图兜底" % (key, r["q"]))
        # ---- no_opts：条带渲染 ----
        for r in d["repairs"]:
            if r.get("type") != "no_opts":
                continue
            sp = r["span"]
            jobs.append(("%s_no%s" % (key, r["q"]), sp["p"], sp["y0"], sp["p1"], sp["y1"]))
        # ---- 无答案：整题渲染 ----
        for q in d["result"].values():
            if not q["answer"] and str(q["id"]) in d.get("meta", {}):
                m = d["meta"][str(q["id"])]
                sr, es = m.get("stem_row"), m.get("expl_start")
                if sr and es:
                    jobs.append(("%s_noans%d" % (key, q["id"]), sr["p"], sr["y0"] - 4,
                                 es["p"], es["y0"] - 4))
        # ---- 真缺号：gap 渲染 ----
        for n in d["missing_no"]:
            if key == "2024地市级" and 101 <= n <= 110:
                continue
            got = sorted(int(k) for k in d["result"])
            prev = max([g for g in got if g < n], default=None)
            nxt = min([g for g in got if g > n], default=None)
            if prev is None or nxt is None or str(nxt) not in d["meta"]:
                continue
            sr = d["meta"][str(nxt)]["stem_row"]
            jobs.append(("%s_gap%d" % (key, n), sr["p"], 0, sr["p"], sr["y0"] - 4))
            # anchor 用 batch_repair 同款：往上找 故正确答案
            d["_gap_%d" % n] = {"p": sr["p"], "y_top": sr["y0"] - 4}
    # gap 的起点需要 anchor；重扫一遍
    sys.path.insert(0, _p("WorkBuddy", "2026-09-19-20-27-33", ".tmp", "gongkao"))
    import parse_zf5 as P
    for key, cfg in PAPERS.items():
        d = json.load(io.open(cfg["parsed"], encoding="utf-8"))
        gaps = [n[6:] if False else k for k in d if k.startswith("_gap_")]
        if not gaps:
            continue
        frags = json.load(io.open(cfg["cache"], encoding="utf-8"))
        rows = P.merge_rows(frags)
        for k in gaps:
            n = int(k.split("_")[-1])
            info = d.pop(k)
            i_nxt = next((i for i, r in enumerate(rows)
                          if r["p"] == info["p"] and abs(r["y0"] - info["y_top"] + 4) < 2), None)
            anchor = None
            if i_nxt:
                for j in range(i_nxt - 1, max(0, i_nxt - 60), -1):
                    if re.search(r"故正确答案|故本题选", rows[j]["t"]):
                        anchor = rows[j]; break
            if anchor:
                jobs.append(("%s_gap%d" % (key, n), anchor["p"], anchor["y1"] + 2,
                             info["p"], info["y_top"]))
            else:
                jobs.append(("%s_gap%d" % (key, n), info["p"], 44, info["p"], info["y_top"]))

    for key, cfg in PAPERS.items():
        if key in doc_cache:
            doc_cache[key].close()
    print("渲染 %d 张条带" % len(jobs))
    doc_map = {}
    for label, p0, y_lo, p1, y_hi in jobs:
        key = label.rsplit("_", 1)[0] if label.startswith("202") and "_no" not in label and "_gap" not in label else label.rsplit("_", 1)[0]
        key = re.match(r"\d+[^_]+", label).group(0)
        if key not in doc_map:
            doc_map[key] = fitz.open(PAPERS[key]["pdf"])
        parts = span_parts(p0, y_lo, p1, y_hi)
        ims = []
        for p, a, b in parts:
            pix = doc_map[key][p].get_pixmap(matrix=fitz.Matrix(120 / 72, 120 / 72),
                                             clip=fitz.Rect(30, max(2, a), 574, min(810, b)), alpha=False)
            ims.append(Image.frombytes("RGB", (pix.width, pix.height), pix.samples))
        out = os.path.join(RENDER, "man_%s.png" % label)
        stack_save(ims, out)
        print("  ", os.path.basename(out), "p%d %.0f-%.0f" % (p0, y_lo, y_hi))
    for d2 in doc_map.values():
        d2.close()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
