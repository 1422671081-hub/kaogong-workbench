# -*- coding: utf-8 -*-
import os as _os
_HOME = _os.environ.get("KG_HOME", _os.path.expanduser("~"))
def _p(*parts):
    return _os.path.join(_HOME, *parts)
"""clip-OCR 自动修补：缺题号行注入 + 缺选项题整块重OCR。修不动的留在 flagged。"""
import io
import json
import os
import re
import sys

import fitz

sys.path.insert(0, _p("WorkBuddy", "2026-09-19-20-27-33", ".tmp", "gongkao"))
from batch_lib import PAPERS, TESS, dered
import parse_zf5 as P

OPT_LINE = re.compile(r"^\s*([A-Da-d0-9OoGQ@]{1,2})\s*[.、．…·]?\s*(\S.*)$")


def strip_ocr(doc, page, y0, y1, dpi=350):
    """裁剪条带 -> 白底大页 -> OCR，返回 (页内相对行, 文本) 列表"""
    rect = fitz.Rect(30, max(2, y0), 574, min(810, y1))
    if rect.height < 6:
        return []
    pix = doc[page].get_pixmap(matrix=fitz.Matrix(dpi / 72.0, dpi / 72.0),
                               clip=rect, alpha=False)
    im = dered(_to_pil(pix))
    t = fitz.open()
    pg = t.new_page(width=595, height=842)
    pg.insert_image(fitz.Rect(30, 380, 30 + rect.width * 72.0 / dpi,
                              380 + rect.height * 72.0 / dpi), pixmap=_pil2pix(im))
    tp = pg.get_textpage_ocr(language="chi_sim", dpi=dpi, full=True, tessdata=TESS)
    d = pg.get_text("dict", textpage=tp)
    out = []
    for b in d.get("blocks", []):
        if b.get("type") != 0:
            continue
        for l in b.get("lines", []):
            txt = "".join(s.get("text", "") for s in l.get("spans", "")).strip()
            if txt:
                out.append((l["bbox"][1], txt))
    t.close()
    out.sort()
    return out


def _to_pil(pix):
    from PIL import Image
    return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)


def _pil2pix(im):
    import tempfile
    f = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    f.close()
    im.save(f.name)
    return fitz.Pixmap(f.name)


def opt_letter_ok(pre):
    low = pre.lower()
    return len(pre) == 1 and low in "abcd" or \
        (len(pre) == 2 and any(c.lower() in "abcd" for c in pre))


def repair_paper(key, cfg):
    d = json.load(io.open(cfg["parsed"], encoding="utf-8"))
    result, meta, repairs = d["result"], d["meta"], d["repairs"]
    frags = json.load(io.open(cfg["cache"], encoding="utf-8"))
    rows = P.merge_rows(frags)
    doc = fitz.open(cfg["pdf"])
    flagged = []

    # ---- 缺题号：条带 OCR 找回题干行并注入 ----
    for n in list(d["missing_no"]):
        got = sorted(int(k) for k in result)
        prev = max([g for g in got if g < n], default=None)
        nxt = min([g for g in got if g > n], default=None)
        if prev is None or nxt is None:
            flagged.append((key, n, "题号边界")); continue
        # 前一题解析末行 -> 本题第一条幸存行（缺的题号行就在中间）
        i_nxt = next((k for k, r in enumerate(rows)
                      if r["p"] == meta[str(nxt)]["stem_row"]["p"]
                      and abs(r["y0"] - meta[str(nxt)]["stem_row"]["y0"]) < 2), None)
        if i_nxt is None:
            flagged.append((key, n, "下一题行未定位")); continue
        anchor = None
        for k in range(i_nxt - 1, max(0, i_nxt - 60), -1):
            if re.search(r"故正确答案|故本题选", rows[k]["t"]):
                anchor = rows[k]; break
        if anchor is None:
            anchor = rows[max(0, i_nxt - 1)]
        lines = strip_ocr(doc, anchor["p"], anchor["y1"] + 2, rows[i_nxt]["y0"] - 2)
        hit = next((t for _, t in lines if re.match(r"^\s*%d\s*[^\d]" % n, t)), None)
        if hit:
            result[str(n)] = {"id": n, "stem": "", "options": {"A": "", "B": "", "C": "", "D": ""},
                              "answer": "", "answer_src": "注入题干行", "explain": "",
                              "page": anchor["p"] + 1, "injected_stem": hit}
            d["missing_no"].remove(n)
            print("  %s 题%d 题干行找回: %s" % (key, n, hit[:40]))
        else:
            flagged.append((key, n, "题干行OCR失败"))

    # ---- 缺选项：整块重 OCR，按行序映射 A-D ----
    for r in repairs:
        if not (r.get("type") == "missing_opt" or "missing" in r):
            continue
        qno = str(r["q"])
        q = result.get(qno)
        if not q:
            continue
        span = r.get("span") or {}
        p, y0, y1 = span.get("p"), span.get("y0"), span.get("y1")
        if p is None:
            flagged.append((key, qno, "无span")); continue
        lines = strip_ocr(doc, p, y0 - 10, y1 + 10)
        opts = []
        for _, t in lines:
            m = OPT_LINE.match(t)
            if m and opt_letter_ok(m.group(1)) and len(t) >= 2:
                opts.append(t.strip())
        if len(opts) >= 4:
            for k, L in enumerate("ABCD"):
                t = opts[k]
                mm = OPT_LINE.match(t)
                q["options"][L] = (mm.group(2) if mm else t).strip()
            r["fixed_by"] = "clip_ocr"
            print("  %s 题%s 选项重OCR: %s" % (key, qno, " / ".join(
                q["options"][L][:10] for L in "ABCD")))
        else:
            flagged.append((key, qno, "选项重OCR仅%d行" % len(opts)))

    doc.close()
    d["flagged"] = flagged
    with io.open(cfg["parsed"], "w", encoding="utf-8") as fp:
        json.dump(d, fp, ensure_ascii=False, indent=1)
    return flagged


def main():
    all_flagged = []
    for key, cfg in PAPERS.items():
        if not os.path.exists(cfg["parsed"]):
            print("==", key, "未解析，跳过"); continue
        print("==", key)
        all_flagged += repair_paper(key, cfg)
    print("\n待人工修补", len(all_flagged), "处:")
    for f in all_flagged:
        print("  ", f)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
