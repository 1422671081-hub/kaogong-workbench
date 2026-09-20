# -*- coding: utf-8 -*-
import os as _os
_HOME = _os.environ.get("KG_HOME", _os.path.expanduser("~"))
def _p(*parts):
    return _os.path.join(_HOME, *parts)
"""把执法卷的图表材料/图形推理题块从 PDF 裁成 PNG，去红（答案标记）后供题库使用。"""
import io
import json
import sys

import fitz
from PIL import Image

sys.path.insert(0, _p("WorkBuddy", "2026-09-19-20-27-33", ".tmp", "gongkao"))
import parse_zf5 as P

PDF = _p("Desktop", "2022年国家公务员录用考试《行测》（行政执法卷）.pdf")
IMGDIR = _p("Desktop", "考公工作台", "img")
DPI = 210
S = DPI / 72.0


def dered(im):
    """红色答案标注 -> 深灰，避免剧透"""
    px = im.load()
    w, h = im.size
    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y][:3]
            if r > 140 and r - g > 40 and r - b > 40:
                px[x, y] = (95, 95, 95)
    return im


def crop(doc, page, y0, y1, dered_it=False):
    pix = doc[page].get_pixmap(matrix=fitz.Matrix(S, S),
                               clip=fitz.Rect(34, y0, 574, y1), alpha=False)
    im = Image.frombytes("RGB" if pix.n == 3 else "RGB",
                         (pix.width, pix.height), pix.samples)
    return dered(im) if dered_it else im


def stack(ims, path):
    w = max(i.width for i in ims)
    h = sum(i.height for i in ims) + 12 * (len(ims) - 1)
    out = Image.new("RGB", (w, h), (255, 255, 255))
    y = 0
    for i in ims:
        out.paste(i, (0, y)); y += i.height + 12
    out.save(path)
    print("  ", path.split("\\")[-1], out.size)


def main():
    doc = fitz.open(PDF)
    frags = json.load(io.open(P.CACHE, encoding="utf-8")) + P.INJECT
    rows = P.merge_rows(frags)
    qidx, _ = P.find_qidx(rows)
    mp = {n: i for i, n in qidx}
    seq = [n for _, n in qidx]

    # ---- 图形推理 71-76：整块（题干图+选项图），去红 ----
    for qno in range(71, 77):
        i = mp[qno]
        end = qidx[seq.index(qno) + 1][0]
        seg = rows[i:end]
        run, j, real = P.grab_options(seg)
        if not run:
            print("!! 题%d 无选项族" % qno); continue
        s = next(k for k, x in enumerate(seg) if x is run[0])
        y_start = seg[0]["y0"] - 6
        # 选项族结束 -> 解析开头之前（解析可能已翻页）
        parts, cur_p, cur_y = [], seg[0]["p"], y_start
        for k in range(s, j):
            r = seg[k]
            if r["p"] != cur_p:                     # 跨页：先截当前页到页尾
                parts.append((cur_p, cur_y, 812)); cur_p, cur_y = r["p"], 44
        if j < len(seg):
            last = seg[j]
            if last["p"] != cur_p:                  # 解析翻页：当前页截到页尾
                parts.append((cur_p, cur_y, 812)); cur_p, cur_y = last["p"], 44
            parts.append((cur_p, cur_y, last["y0"] - 4))
        else:
            parts.append((cur_p, cur_y, 812))
        ims = [crop(doc, p_, a, b, dered_it=True) for p_, a, b in parts]
        stack(ims, IMGDIR + r"\zf_fig_%d.png" % qno)

    # ---- 资料分析材料图 ----
    jobs = [
        ("zf_mat_111.png",  [(68, 24, 470)], False),
        ("zf_mat_116a.png", [(70, 160, 494)], False),
        ("zf_mat_116b.png", [(71, 14, 232)], False),
        ("zf_mat_121.png",  [(73, 415, 648)], False),
        ("zf_q120.png",     [(73, 66, 176)], False),
        ("zf_q86a.png",     [(50, 676, 816)], True),
        ("zf_q86b.png",     [(51, 16, 278)], True),
    ]
    for name, parts, dr in jobs:
        ims = [crop(doc, p_, a, b, dered_it=dr) for p_, a, b in parts]
        if len(ims) == 1:
            ims[0].save(IMGDIR + "\\" + name)
            print("  ", name, ims[0].size)
        else:
            stack(ims, IMGDIR + "\\" + name)
    doc.close()
    print("裁图完成")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
