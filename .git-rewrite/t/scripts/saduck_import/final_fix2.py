# -*- coding: utf-8 -*-
import os as _os
_HOME = _os.environ.get("KG_HOME", _os.path.expanduser("~"))
def _p(*parts):
    return _os.path.join(_HOME, *parts)
"""对 9 组污染材料图用 explain 子串法重裁；跨组共用补挂；opt 图挂载。"""
import io
import json
import os
import re
import sys

import fitz

sys.path.insert(0, _p("WorkBuddy", "2026-09-19-20-27-33", ".tmp", "gongkao"))
from batch_lib import PAPERS, IMGDIR, crop, stack_save
import parse_zf5 as P

QNO = re.compile(r"^\s*(\d{1,3})\s*[^\d\u4e00-\u9fff]{0,3}\s*(\S.*)$")
TARGETS = {
    "2023地市级": [116, 121], "2023副省级": [131], "2023行政执法": [121],
    "2025副省级": [126], "2026地市级": [116], "2026行政执法": [116],
}
norm = lambda s: re.sub(r"[\s，。；：、“”‘’()（）]", "", s)


def find_expl_end(rows, idx, explain_norm, max_back=400):
    """从组首题号行往上找「去空格文本是 explain 子串」的最大 k（最靠近 f 的解析行）"""
    hit = None
    for k in range(idx - 1, max(0, idx - max_back), -1):
        t = norm(rows[k]["t"])
        if len(t) >= 10 and t in explain_norm:
            hit = k
            break
    return hit


def main():
    log = []
    for key, groups in TARGETS.items():
        cfg = PAPERS[key]
        d = json.load(io.open(cfg["parsed"], encoding="utf-8"))
        bank = {q["id"]: q for q in d["bank"]}
        result = d["result"]
        frags = json.load(io.open(cfg["cache"], encoding="utf-8"))
        rows = P.merge_rows(frags)
        doc = fitz.open(cfg["pdf"])
        for f in groups:
            if str(f) not in d["meta"] or str(f - 1) not in result:
                log.append("!! %s mat_%d 缺前置" % (key, f)); continue
            sr = d["meta"][str(f)]["stem_row"]
            idx = next((k for k, r in enumerate(rows)
                        if r["p"] == sr["p"] and abs(r["y0"] - sr["y0"]) < 2), None)
            if idx is None:
                log.append("!! %s mat_%d 题号行未定位" % (key, f)); continue
            explain_norm = norm(result[str(f - 1)].get("explain", ""))
            if len(explain_norm) < 40:
                log.append("!! %s mat_%d 上题解析过短" % (key, f)); continue
            k = find_expl_end(rows, idx, explain_norm)
            if k is None:
                log.append("!! %s mat_%d 子串未命中" % (key, f)); continue
            a = rows[k]
            log.append("%s mat_%d 锚点 p%d y%.0f「%s」" % (key, f, a["p"], a["y0"], a["t"][:24]))
            if a["p"] == sr["p"]:
                parts = [(a["p"], a["y1"] + 8, sr["y0"] - 5)]
            else:
                parts = [(a["p"], a["y1"] + 8, 806)] + \
                        [(p, 44, 806) for p in range(a["p"] + 1, sr["p"])] + \
                        [(sr["p"], 44, sr["y0"] - 5)]
            ims = [crop(doc, p, x, y) for p, x, y in parts]
            fn = "zf2_%s_mat_%d.png" % (key, f)
            if stack_save(ims, os.path.join(IMGDIR, fn)):
                for q in d["bank"]:
                    if f <= q["id"] < f + 5:
                        q["imgs"] = [fn]
            else:
                log.append("!! %s mat_%d 裁剪失败" % (key, f))
        doc.close()
        with io.open(cfg["parsed"], "w", encoding="utf-8") as fp:
            json.dump(d, fp, ensure_ascii=False, indent=1)

    # 2026地市 121-125：科幻材料手工区间（p78 208-750）
    cfg = PAPERS["2026地市级"]
    d = json.load(io.open(cfg["parsed"], encoding="utf-8"))
    doc = fitz.open(cfg["pdf"])
    im = crop(doc, 78, 208, 750)
    fn = "zf2_2026地市级_mat_121.png"
    im.save(os.path.join(IMGDIR, fn))
    for q in d["bank"]:
        if 121 <= q["id"] <= 125:
            q["imgs"] = [fn]
    doc.close()
    with io.open(cfg["parsed"], "w", encoding="utf-8") as fp:
        json.dump(d, fp, ensure_ascii=False, indent=1)
    log.append("2026地市级 121-125 手工裁科幻材料 p78 208-750")

    # 2026副省 131-135 复用 mat_126
    cfg = PAPERS["2026副省级"]
    d = json.load(io.open(cfg["parsed"], encoding="utf-8"))
    for q in d["bank"]:
        if 131 <= q["id"] <= 135:
            q["imgs"] = ["zf2_2026副省级_mat_126.png"]
    with io.open(cfg["parsed"], "w", encoding="utf-8") as fp:
        json.dump(d, fp, ensure_ascii=False, indent=1)
    log.append("2026副省级 131-135 复用 mat_126")

    # opt 兜底图挂载
    n_opt = 0
    for key, cfg in PAPERS.items():
        d = json.load(io.open(cfg["parsed"], encoding="utf-8"))
        bank = {q["id"]: q for q in d["bank"]}
        changed = False
        for f in os.listdir(IMGDIR):
            m = re.match(r"zf2_(.+)_opt_(\d+)\.png$", f)
            if not m or m.group(1) != key:
                continue
            q = bank.get(int(m.group(2)))
            if q is None:
                continue
            if f not in (q.get("imgs") or []):
                q.setdefault("imgs", []).append(f)
                changed = True; n_opt += 1
            for L in "ABCD":
                if q["options"].get(L) == "(待校)":
                    q["options"][L] = "(见图)"
        if changed:
            with io.open(cfg["parsed"], "w", encoding="utf-8") as fp:
                json.dump(d, fp, ensure_ascii=False, indent=1)
    log.append("opt 兜底图挂载 %d 张" % n_opt)
    print("\n".join(log))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
