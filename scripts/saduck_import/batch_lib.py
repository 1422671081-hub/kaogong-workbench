# -*- coding: utf-8 -*-
import os as _os
_HOME = _os.environ.get("KG_HOME", _os.path.expanduser("~"))
def _p(*parts):
    return _os.path.join(_HOME, *parts)
"""12 套 SaDuck 卷批量录入：公共库。2023-2026 × 地市级/副省级/行政执法卷。"""
import io
import json
import os
import re
import sys

import fitz
from PIL import Image

HERE = _p("WorkBuddy", "2026-09-19-20-27-33", ".tmp", "gongkao")
sys.path.insert(0, HERE)
import parse_zf5 as P          # 复用 merge_rows/is_opt/grab_options/fill_missing/EXPL_HEAD

TESS = os.path.join(HERE, "tessdata")
BATCH = os.path.join(HERE, "batch")
IMGDIR = _p("Desktop", "考公工作台", "img")
STORE = _p("Desktop", "考公工作台")
PDFDIR = _p("Desktop", "题库")
DPI = 210

# 卷配置：key -> (文件名, 总题数, 数量关系上限, 判断推理上限)
PAPERS = {}
SUFFIX = {2023: "行政执法", 2024: "行政执法卷", 2025: "行政执法卷", 2026: "行政执法"}
for y in (2023, 2024, 2025, 2026):
    suffix = SUFFIX[y]
    for kind, fn, total, n_end, j_end in (
        ("地市级", "地市级", 130, 70, 110),
        ("副省级", "副省级", 135, 75, 115),
        ("行政执法卷", suffix, 130, 70, 110),
    ):
        key = "%d%s" % (y, kind[:-1] if kind == "行政执法卷" else kind)
        PAPERS[key] = {
            "key": key, "paper": "%d国考%s" % (y, kind),
            "pdf": os.path.join(PDFDIR, "%d年国家公务员录用考试《行测》（%s）.pdf" % (y, fn)),
            "total": total, "num_end": n_end, "jg_end": j_end,
            "cache": os.path.join(BATCH, key, "lines.json"),
            "parsed": os.path.join(BATCH, key, "parsed.json"),
        }

QNO = re.compile(r"^\s*(\d{1,3})\s*[^\d\u4e00-\u9fff]{0,3}\s*(\S.*)$")
FIG_STEM = re.compile(r"规律性|截面|展开图|立体图形|折纸|纸盒|折成|折叠")
CHART_STEM = re.compile("折线图|饼图|柱状图|扇形图|哪个图|哪一类图|所示的概率")
SAFE_FIX = [
    ("完法", "宪法"), ("罗辑", "逻辑"),
    ("友展", "发展"), ("友生", "发生"), ("友射", "发射"), ("友挥", "发挥"),
    ("友现", "发现"), ("友布", "发布"), ("友言", "发言"), ("友掘", "发掘"),
    ("人否", "能否"), ("人台", "5台"),
]


def fix(s):
    if not s:
        return s
    for a, b in SAFE_FIX:
        s = s.replace(a, b)
    return s


def part_of(cfg, n):
    if n <= 20:
        return "常识判断"
    if n <= 60:
        return "言语理解"
    if n <= cfg["num_end"]:
        return "数量关系"
    if n <= cfg["jg_end"]:
        return "判断推理"
    return "资料分析"


def sub_of(stem, opts):
    if FIG_STEM.search(stem):
        return "图形推理"
    if re.search(r"根据上述定义|下列属于|不符合这一定义|定义的关键词", stem):
        return "定义判断"
    if len(stem) <= 16 and "：" in stem or ("：" in stem and len(opts.get("A", "")) <= 12 and "：" in opts.get("A", "")):
        return "类比推理"
    return "逻辑判断"


# ---------- OCR 缓存（与 cache_lines 相同逻辑，参数化路径） ----------
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


NOISE = [
    re.compile(r"SaDuck", re.I), re.compile(r"历年试卷"),
    re.compile(r"saduck\.top", re.I), re.compile(r"^\s*\d{4}\s*/\s*\d{1,2}\s*/\s*\d{1,2}"),
    re.compile(r"^\s*\d+\s*/\s*\d+\s*$"), re.compile(r"^\s*\d{1,5}\s*$"),
]


def cache_paper(cfg):
    if os.path.exists(cfg["cache"]):
        return
    os.makedirs(os.path.dirname(cfg["cache"]), exist_ok=True)
    doc = fitz.open(cfg["pdf"])
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
                if not txt or any(p.match(txt) for p in NOISE):
                    continue
                x0, y0, x1, y1 = l["bbox"]
                yc = (y0 + y1) / 2
                out.append({"p": pno, "y0": round(y0, 1), "y1": round(y1, 1),
                            "x0": round(x0, 1), "x1": round(x1, 1), "t": txt,
                            "red": any(a - 7 <= yc <= b2 + 7 for (a, b2) in reds)})
        sys.stdout.write("\r  %s %d/%d" % (cfg["key"], pno + 1, doc.page_count))
        sys.stdout.flush()
    doc.close()
    with io.open(cfg["cache"], "w", encoding="utf-8") as fp:
        json.dump(out, fp, ensure_ascii=False)
    print("  缓存 %d 行" % len(out))


# ---------- 解析（find_qidx 参数化版） ----------
def find_qidx(rows, total):
    cand = []
    for i, r in enumerate(rows):
        m = QNO.match(r["t"])
        if not m:
            continue
        n = int(m.group(1))
        if 1 <= n <= total and r["x0"] <= P.QNO_X and len(m.group(2)) >= 4:
            cand.append((i, n))
    picked, target, k = [], 1, 0
    while k < len(cand) and target <= total:
        i, n = cand[k]
        if n == target:
            picked.append((i, n)); target += 1; k += 1
        elif target < n <= target + 2:
            target = n; picked.append((i, n)); target += 1; k += 1
        else:
            k += 1
    have = {n for _, n in picked}
    used = {i for i, _ in picked}
    for t in range(1, total + 1):
        if t in have:
            continue
        for i, n in cand:
            if n == t and i not in used:
                picked.append((i, n)); used.add(i); break
    picked.sort()
    return picked, cand


def dered(im):
    px = im.load()
    for y in range(im.height):
        for x in range(im.width):
            r, g, b = px[x, y][:3]
            if r > 140 and r - g > 40 and r - b > 40:
                px[x, y] = (95, 95, 95)
    return im


def crop(doc, page, y0, y1, dr=True):
    y0 = max(2.0, y0); y1 = min(812.0, y1)
    if y1 - y0 < 8:
        return None
    pix = doc[page].get_pixmap(matrix=fitz.Matrix(DPI / 72.0, DPI / 72.0),
                               clip=fitz.Rect(34, y0, 574, y1), alpha=False)
    im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    return dered(im) if dr else im


def stack_save(ims, path):
    ims = [i for i in ims if i is not None]
    if not ims:
        return False
    if len(ims) == 1:
        ims[0].save(path)
    else:
        w = max(i.width for i in ims)
        h = sum(i.height for i in ims) + 12 * (len(ims) - 1)
        out = Image.new("RGB", (w, h), (255, 255, 255))
        y = 0
        for i in ims:
            out.paste(i, (0, y)); y += i.height + 12
        out.save(path)
    return True


def span_parts(rows_in_span):
    """(首行, 尾行) -> 跨页分段 [(p, y_lo, y_hi)]，续页避开页眉"""
    if not rows_in_span:
        return []
    (p0, y_lo), (p1, y_hi) = rows_in_span
    if p0 == p1:
        return [(p0, y_lo, y_hi)] if y_hi - y_lo >= 8 else []
    parts = [(p0, y_lo, 806)]
    for p in range(p0 + 1, p1):
        parts.append((p, 44, 806))
    if y_hi - 44 >= 8:
        parts.append((p1, 44, y_hi))
    return parts
