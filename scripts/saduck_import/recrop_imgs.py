# -*- coding: utf-8 -*-
import os as _os
_HOME = _os.environ.get("KG_HOME", _os.path.expanduser("~"))
def _p(*parts):
    return _os.path.join(_HOME, *parts)
"""用 OCR 行缓存的真实坐标重裁资料分析/定义判断配图（目测坐标系统性偏移，废弃）。"""
import io
import json
import re
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
    px = im.load()
    for y in range(im.height):
        for x in range(im.width):
            r, g, b = px[x, y][:3]
            if r > 140 and r - g > 40 and r - b > 40:
                px[x, y] = (95, 95, 95)
    return im


def crop(doc, page, y0, y1, dr=False):
    y0 = max(2.0, y0); y1 = min(812.0, y1)
    pix = doc[page].get_pixmap(matrix=fitz.Matrix(S, S),
                               clip=fitz.Rect(34, y0, 574, y1), alpha=False)
    im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    return dered(im) if dr else im


def main():
    frags = json.load(io.open(P.CACHE, encoding="utf-8")) + P.INJECT
    rows = P.merge_rows(frags)

    def find(page, pat, last=False):
        rx = re.compile(pat)
        hits = [r for r in rows if r["p"] == page and rx.search(r["t"])]
        if not hits:
            raise SystemExit("!! p%d 找不到锚点 %s" % (page, pat))
        return hits[-1] if last else hits[0]

    def first_content(page, ymin=40.0):
        hits = [r for r in rows if r["p"] == page and r["y0"] > ymin]
        return hits[0] if hits else None

    jobs = []

    # 111 材料：标题行 -> 111 题号行
    t = find(68, r"2021 ?年第一季度市场监管部门")
    e = find(68, r"^111[\s.．、]")
    jobs.append(("zf_mat_111.png", [(68, t["y0"] - 10, e["y0"] - 8)], False))

    # 116 材料 a：文字材料行 -> 表格底（表格行大部分没被 OCR，用 p70 最后一条内容行的底边）
    t = find(70, r"2020年12 ?月，全国")
    tail = [r for r in rows if r["p"] == 70 and r["y0"] > 260]
    y_end = max(r["y1"] for r in tail) + 18
    jobs.append(("zf_mat_116a.png", [(70, t["y0"] - 8, y_end)], False))

    # 116 材料 b：p71 图顶部(件 标签) -> 图标题底（OCR 把受理认成这理）
    t = [r for r in rows if r["p"] == 71 and r["y0"] > 26][0]
    e = find(71, r"年各月环保举报")
    jobs.append(("zf_mat_116b.png", [(71, max(27.0, t["y0"] - 6), e["y1"] + 10)], False))

    # 121 材料：亿元 行 -> 121 题号行
    t = find(73, r"亿元")
    e = find(73, r"^121[\s.．、]")
    jobs.append(("zf_mat_121.png", [(73, t["y0"] - 8, e["y0"] - 8)], False))

    # 120 题干折线图：120 题干行底 -> A 选项行
    t = find(73, r"^120[\s.．、]")
    e = find(73, r"A[.、．]\s*电话举报")
    jobs.append(("zf_q120.png", [(73, t["y1"] + 6, e["y0"] - 6)], False))

    # 86 表格选项 a/b
    t = find(50, r"^86[\s.．、]")
    jobs.append(("zf_q86a.png", [(50, t["y1"] + 6, 806)], True))
    t_expl = find(51, r"第一步[:：]")
    jobs.append(("zf_q86b.png", [(51, 27, t_expl["y0"] - 8)], True))

    doc = fitz.open(PDF)
    for name, parts, dr in jobs:
        ims = []
        for p_, a, b in parts:
            im = crop(doc, p_, a, b, dr=dr)
            ims.append(im)
            print("%s  p%d %.0f-%.0f  -> %dx%d" % (name, p_, a, b, im.width, im.height))
        if len(ims) == 1:
            ims[0].save(IMGDIR + "\\" + name)
        else:
            w = max(i.width for i in ims)
            h = sum(i.height for i in ims) + 12 * (len(ims) - 1)
            out = Image.new("RGB", (w, h), (255, 255, 255))
            y = 0
            for i in ims:
                out.paste(i, (0, y)); y += i.height + 12
            out.save(IMGDIR + "\\" + name)
    doc.close()
    print("重裁完成")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
