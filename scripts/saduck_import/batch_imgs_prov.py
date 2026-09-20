# -*- coding: utf-8 -*-
import os as _os
_HOME = _os.environ.get("KG_HOME", _os.path.expanduser("~"))
def _p(*parts):
    return _os.path.join(_HOME, *parts)
"""省考卷批量配图：图形推理整题图 + 资料材料图 + 选项空题兜底图（JPEG 压缩）。"""
import io
import json
import os
import re
import sys

import fitz
from PIL import Image

sys.path.insert(0, _p("WorkBuddy", "2026-09-19-20-27-33", ".tmp", "gongkao"))
from batch_lib import crop

PROV = _p("WorkBuddy", "2026-09-19-20-27-33", ".tmp", "gongkao", "prov")
IMGDIR = _p("Desktop", "考公工作台", "img")
DPI = 170
JQ = 78

QNO = re.compile(r"^(\d{1,3})\s*[.、．]?\s*(\S.*)$")
FIG_STEM = re.compile(r"规律性|截面|展开图|立体图形|折纸|纸盒|折叠成")


def norm(s):
    return re.sub(r"[\s，。；：、“”‘’()（）·]", "", s or "")


def l2_yanyu(stem):
    if re.search(r"填入画横线|依次填入|填入横线|横线部分最恰当|适合填入", stem):
        return "逻辑填空"
    if re.search(r"重新排列|语序正确|句子排序|语句顺序|还原句子|语句复位", stem):
        return "语句表达"
    return "片段阅读"


L2_ZL = [("综合分析", r"能够从上述资料中推出|以下说法正确的是|以下信息中，能够|可以推出"),
         ("两期比重计算", r"两期比重"), ("现期比重计算", r"现期比重"),
         ("比重比较", r"比重.{0,6}比较|比较.{0,6}比重"), ("基期量计算", r"基期量"),
         ("增长量计算", r"增长量.{0,8}计算|增长量约为|增长量为"),
         ("增长量比较", r"增长量.{0,8}比较|增量.{0,6}最大|增量.{0,6}最小"),
         ("平均数计算", r"平均数|平均每|月均|日均"), ("倍数计算", r"倍数|多少倍|几倍"),
         ("增长率比较", r"增长率.{0,8}比较|同比增速最快|增速最快"),
         ("简单计算", r"简单计算"), ("简单比较", r"简单比较"),
         ("读数比较", r"读数比较"), ("和差比较", r"和差")]


def l2_ziliao(stem, explain):
    if re.search(r"能够从上述资料中推出|以下说法正确的是|以下信息中，能够", stem):
        return "综合分析"
    text = (explain[:160] or "") + " " + stem[:80]
    for name, pat in L2_ZL:
        if re.search(pat, text):
            return name
    return ""


def sub_of(stem):
    if FIG_STEM.search(stem):
        return "图形推理"
    if re.search(r"根据上述定义|下列属于|不符合这一定义|定义的关键词", stem):
        return "定义判断"
    if len(stem) <= 16 and "：" in stem:
        return "类比推理"
    return "逻辑判断"


def save_jpg(ims, path):
    ims = [i for i in ims if i is not None]
    if not ims:
        return False
    if len(ims) == 1:
        im = ims[0]
    else:
        w = max(i.width for i in ims)
        h = sum(i.height for i in ims) + 8 * (len(ims) - 1)
        im = Image.new("RGB", (w, h), (255, 255, 255))
        y = 0
        for i in ims:
            im.paste(i, (0, y)); y += i.height + 8
    im.save(path, "JPEG", quality=JQ)
    return True


def span_parts(p0, y_lo, p1, y_hi):
    if p0 == p1:
        return [(p0, y_lo, y_hi)] if y_hi - y_lo >= 8 else []
    parts = [(p0, y_lo, 806)]
    for p in range(p0 + 1, p1):
        parts.append((p, 42, 806))
    if y_hi - 42 >= 8:
        parts.append((p1, 42, y_hi))
    return parts


def build_lines(doc):
    out = []
    for pno in range(doc.page_count):
        dd = doc[pno].get_text("dict")
        for b in dd.get("blocks", []):
            if b.get("type") != 0:
                continue
            for l in b.get("lines", []):
                t = "".join(s.get("text", "") for s in l.get("spans", "")).strip()
                if not t or re.search(r"全部题目-常规|公务员录用考试《行测》|国家《行测》题", t):
                    continue
                x0, y0, _, _ = l["bbox"]
                out.append({"p": pno, "y0": round(y0, 1), "x0": round(x0, 1), "t": t})
    out.sort(key=lambda r: (r["p"], r["y0"], r["x0"]))
    rows, cur = [], []
    for r in out:
        if cur and r["p"] == cur[0]["p"] and abs(r["y0"] - cur[0]["y0"]) <= 3:
            cur.append(r)
        else:
            if cur:
                rows.append(cur)
            cur = [r]
    if cur:
        rows.append(cur)
    mrows = []
    for g in rows:
        g.sort(key=lambda r: r["x0"])
        t = g[0]["t"]
        for nxt in g[1:]:
            sep = " " if (t[-1:].isascii() and t[-1:].isalnum() and nxt["t"][:1].isascii()) else ""
            t += sep + nxt["t"]
        tt = re.sub(r"\s+", " ", t).strip()
        if re.fullmatch(r"\d{1,2}", tt) and g[0]["x0"] > 500:
            continue
        mrows.append({"p": g[0]["p"], "y0": g[0]["y0"], "x0": g[0]["x0"], "t": tt})
    return mrows


def main(only_prov=None):
    files = sorted(os.listdir(PROV))
    if only_prov:
        files = [f for f in files if only_prov in f]
    n_total = 0
    for fi, fn in enumerate(files):
        d = json.load(io.open(os.path.join(PROV, fn), encoding="utf-8"))
        if d.get("error"):
            continue
        paper = d["paper"]
        result = d["result"]
        total = d["total"]
        doc = fitz.open(d["file"])
        mrows = build_lines(doc)
        pos = {}
        for r in mrows:
            m = QNO.match(r["t"])
            if m and r["x0"] < 60 and len(r["t"]) < 90:
                n = int(m.group(1))
                if 1 <= n <= total and n not in pos:
                    pos[n] = (r["p"], r["y0"])
        n_img = 0
        for n in range(1, total + 1):
            q = result[str(n)]
            stem, opts = q["stem"], q["options"]
            part = q.get("part", "")
            vals = [opts.get(L, "") for L in "ABCD"]
            is_fig = FIG_STEM.search(stem)
            all_short = all(0 < len(norm(v)) <= 2 for v in vals)
            need_blk = any(not v for v in vals)
            if (is_fig and all_short) or (is_fig and need_blk):
                nxt = next((m for m in sorted(pos) if m > n), total + 1)
                a = pos.get(n)
                bpos = pos.get(nxt)
                if not a or not bpos:
                    continue
                parts = span_parts(a[0], a[1] - 4, bpos[0], bpos[1] - 4)
                fn2 = "zf5_%s_fig_%d.jpg" % (paper, n)
                if save_jpg([crop(doc, p, x, y) for p, x, y in parts],
                            os.path.join(IMGDIR, fn2)):
                    q["qimg"] = fn2; q["fig"] = True
                    for L in "ABCD":
                        if len(norm(opts.get(L, ""))) <= 2 or not opts.get(L):
                            opts[L] = "(见图)"
                    n_img += 1
            elif need_blk:
                nxt = next((m for m in sorted(pos) if m > n), total + 1)
                a = pos.get(n)
                bpos = pos.get(nxt)
                if not a or not bpos:
                    continue
                parts = span_parts(a[0], a[1] - 4, bpos[0], bpos[1] - 4)
                fn2 = "zf5_%s_blk_%d.jpg" % (paper, n)
                if save_jpg([crop(doc, p, x, y) for p, x, y in parts],
                            os.path.join(IMGDIR, fn2)):
                    q["qimg"] = fn2
                    for L in "ABCD":
                        if not opts.get(L):
                            opts[L] = "(见图)"
                    n_img += 1
            if part == "资料分析" and not q.get("l2"):
                q["l2"] = l2_ziliao(stem, q["explain"])
            if part == "言语理解" and not q.get("l2"):
                q["l2"] = l2_yanyu(stem)
            if part == "判断推理" and not q.get("sub"):
                q["sub"] = sub_of(stem)

        # 资料分析材料图：part=资料分析 的题号按 5 分组
        zl = sorted(int(k) for k, v in result.items() if v.get("part", "") == "资料分析")
        if zl:
            groups = [zl[i:i + 5] for i in range(0, len(zl), 5)]
            for gi, grp in enumerate(groups):
                f, last_prev = grp[0], (grp[-1] + 1)
                prev_n = grp[0] - 1
                if f not in pos or prev_n not in pos:
                    continue
                a, b = pos[prev_n], pos[f]
                parts = span_parts(a[0], a[1] + 6, b[0], b[1] - 4)
                fn2 = "zf5_%s_mat_%d.jpg" % (paper, f)
                if save_jpg([crop(doc, p, x, y) for p, x, y in parts],
                            os.path.join(IMGDIR, fn2)):
                    for n in grp:
                        result[str(n)]["imgs"] = [fn2]
                    n_img += 1
        doc.close()
        with io.open(os.path.join(PROV, fn), "w", encoding="utf-8") as fp:
            json.dump(d, fp, ensure_ascii=False)
        n_total += n_img
        print("[%d/%d] %s 配图 %d" % (fi + 1, len(files), paper, n_img))
        sys.stdout.flush()
    print("全部配图", n_total, "张")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
