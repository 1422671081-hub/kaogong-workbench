# -*- coding: utf-8 -*-
import os as _os
_HOME = _os.environ.get("KG_HOME", _os.path.expanduser("~"))
def _p(*parts):
    return _os.path.join(_HOME, *parts)
"""把 OCR 坐标行缓存下来，后续调试不再重跑 OCR。"""
import fitz
import io
import json
import os
import re
import sys

PDF = _p("Desktop", "2022年国家公务员录用考试《行测》（行政执法卷）.pdf")
TESS = _p("WorkBuddy", "2026-09-19-20-27-33", ".tmp", "gongkao", "tessdata")
CACHE = _p("WorkBuddy", "2026-09-19-20-27-33", ".tmp", "gongkao", "zf_lines.json")

NOISE = [
    re.compile(r"^\s*\d{4}\s*/\s*\d{1,2}\s*/\s*\d{1,2}\s+\d{1,2}:\d{2}\s*$"),
    re.compile(r"^\s*历年试卷\s*\|?\s*SaDuck.*$", re.I),
    re.compile(r"^\s*https?:?\s*/+\s*saduck\.top.*$", re.I),
    re.compile(r"^\s*\d+\s*/\s*\d+\s*$"),
]


def is_red(c):
    return bool(c) and c[0] > 0.85 and c[1] < 0.25 and c[2] < 0.25


def red_rows(page):
    rects = []
    for d in page.get_drawings():
        if is_red(d.get("fill")) or is_red(d.get("color")):
            r = d["rect"]
            if r.width > 0 and r.height > 0:
                rects.append(r)
    if not rects:
        return []
    rects.sort(key=lambda r: r.y0)
    groups, cur = [], [rects[0]]
    for r in rects[1:]:
        if r.y0 < cur[-1].y1 + 6:
            cur.append(r)
        else:
            groups.append(cur); cur = [r]
    groups.append(cur)
    return [(min(x.y0 for x in g), max(x.y1 for x in g)) for g in groups]


def main():
    if os.path.exists(CACHE):
        print("缓存已存在，跳过 OCR：", CACHE)
        return
    doc = fitz.open(PDF)
    out = []
    for pno in range(doc.page_count):
        page = doc[pno]
        tp = page.get_textpage_ocr(language="chi_sim", dpi=300, full=True, tessdata=TESS)
        d = page.get_text("dict", textpage=tp)
        reds = red_rows(page)
        for b in d.get("blocks", []):
            if b.get("type") != 0:
                continue
            for l in b.get("lines", []):
                txt = "".join(s.get("text", "") for s in l.get("spans", "")).strip()
                if not txt:
                    continue
                if any(p.match(txt) for p in NOISE):
                    continue
                x0, y0, x1, y1 = l["bbox"]
                yc = (y0 + y1) / 2
                red = any(a - 7 <= yc <= b2 + 7 for (a, b2) in reds)
                out.append({"p": pno, "y0": round(y0, 1), "y1": round(y1, 1),
                            "x0": round(x0, 1), "x1": round(x1, 1),
                            "t": txt, "red": red})
        sys.stdout.write("\r  %d/%d" % (pno + 1, doc.page_count)); sys.stdout.flush()
    doc.close()
    print()
    with io.open(CACHE, "w", encoding="utf-8") as fp:
        json.dump(out, fp, ensure_ascii=False)
    print("缓存 %d 行 -> %s" % (len(out), CACHE))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
