# -*- coding: utf-8 -*-
import os as _os
_HOME = _os.environ.get("KG_HOME", _os.path.expanduser("~"))
def _p(*parts):
    return _os.path.join(_HOME, *parts)
"""批量配图：图形推理整题图、资料分析材料图（按组）、图表题干图。全部去红。"""
import io
import json
import os
import re
import sys

sys.path.insert(0, _p("WorkBuddy", "2026-09-19-20-27-33", ".tmp", "gongkao"))
import fitz
from batch_lib import PAPERS, FIG_STEM, CHART_STEM, crop, stack_save
import parse_zf5 as P

IMGDIR = _p("Desktop", "考公工作台", "img")


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
    total_imgs = 0
    for key, cfg in PAPERS.items():
        d = json.load(io.open(cfg["parsed"], encoding="utf-8"))
        bank, meta, result = d["bank"], d["meta"], d["result"]
        frags = json.load(io.open(cfg["cache"], encoding="utf-8"))
        rows = P.merge_rows(frags)
        doc = fitz.open(cfg["pdf"])
        n = 0

        # ---- 图形推理：整题图（题号行 -> 解析首行） ----
        for q in bank:
            if q.get("figimg"):
                m = meta[str(q["id"])]
                sr, es = m["stem_row"], m.get("expl_start")
                if not es:
                    continue
                parts = span_parts(sr["p"], sr["y0"] - 5, es["p"], es["y0"] - 4)
                ims = [crop(doc, p, a, b) for p, a, b in parts]
                fn = "zf2_%s_fig_%d.png" % (key, q["id"])
                if stack_save(ims, os.path.join(IMGDIR, fn)):
                    q["qimg"] = fn; q["fig"] = True
                    q["options"] = {L: "(见图)" for L in "ABCD"}
                    del q["figimg"]; n += 1

        # ---- 资料分析：按组裁材料图（组首题号行前的 最近「故正确答案」行 -> 组首题号行） ----
        s0 = cfg["jg_end"] + 1
        firsts = list(range(s0, cfg["total"] + 1, 5))
        for f in firsts:
            if str(f) not in meta:
                continue
            sr = meta[str(f)]["stem_row"]
            # 组首题号行在 rows 中的下标
            idx = next((k for k, r in enumerate(rows)
                        if r["p"] == sr["p"] and abs(r["y0"] - sr["y0"]) < 2), None)
            if idx is None:
                continue
            anchor = None
            for k in range(idx - 1, max(0, idx - 80), -1):
                if re.search(r"故正确答案|故本题选|综上", rows[k]["t"]):
                    anchor = rows[k]; break
            if anchor is None:
                anchor = rows[max(0, idx - 1)]
            parts = span_parts(anchor["p"], anchor["y1"] + 8, sr["p"], sr["y0"] - 5)
            ims = [crop(doc, p, a, b) for p, a, b in parts]
            fn = "zf2_%s_mat_%d.png" % (key, f)
            if stack_save(ims, os.path.join(IMGDIR, fn)):
                for q in bank:
                    if s0 <= q["id"] < f + 5:
                        q.setdefault("imgs", []).append(fn)
                n += 1

        # ---- 资料分析里带图表的题干（如折线图比较） ----
        for q in bank:
            if q["part"] == "资料分析" and CHART_STEM.search(q["stem"]) and str(q["id"]) in meta:
                m = meta[str(q["id"])]
                if not m.get("opt_first") or not m.get("stem_row"):
                    continue
                of, sr = m["opt_first"], m["stem_row"]
                if of["p"] != sr["p"]:
                    continue
                im = crop(doc, sr["p"], sr["y1"] + 6, of["y0"] - 6, dr=False)
                if im is not None:
                    fn = "zf2_%s_q_%d.png" % (key, q["id"])
                    im.save(os.path.join(IMGDIR, fn))
                    q["qimg"] = fn; n += 1

        doc.close()
        with io.open(cfg["parsed"], "w", encoding="utf-8") as fp:
            json.dump(d, fp, ensure_ascii=False, indent=1)
        total_imgs += n
        print("%s 配图 %d 张" % (key, n))
    print("全部配图", total_imgs, "张")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
