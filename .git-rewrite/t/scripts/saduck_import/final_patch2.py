# -*- coding: utf-8 -*-
import os as _os
_HOME = _os.environ.get("KG_HOME", _os.path.expanduser("~"))
def _p(*parts):
    return _os.path.join(_HOME, *parts)
"""最终补丁：6 组人工定界材料图 + 跨组复用核对 + opt 兜底图挂载 + 全面验证。"""
import io
import json
import os
import re
import sys

import fitz

sys.path.insert(0, _p("WorkBuddy", "2026-09-19-20-27-33", ".tmp", "gongkao"))
from batch_lib import PAPERS, IMGDIR, crop, stack_save

# 人工定界（目检渲染图确定）：key -> f -> [(page, y0, y1), ...]
MANUAL = {
    "2023地市级": {
        116: [(73, 36, 544)],
        121: [(76, 40, 810), (77, 40, 301)],
    },
    "2023行政执法": {
        121: [(72, 40, 810), (73, 40, 810), (74, 40, 301)],
    },
    "2025副省级": {
        126: [(76, 40, 692)],
    },
    "2026地市级": {
        116: [(75, 345, 810), (76, 40, 337)],
    },
    "2026行政执法": {
        116: [(76, 425, 810), (77, 40, 586)],
    },
}


def main():
    for key, groups in MANUAL.items():
        cfg = PAPERS[key]
        d = json.load(io.open(cfg["parsed"], encoding="utf-8"))
        doc = fitz.open(cfg["pdf"])
        for f, parts in groups.items():
            ims = [crop(doc, p, a, b) for p, a, b in parts]
            fn = "zf2_%s_mat_%d.png" % (key, f)
            if stack_save(ims, os.path.join(IMGDIR, fn)):
                for q in d["bank"]:
                    if f <= q["id"] < f + 5:
                        q["imgs"] = [fn]
                print("%s mat_%d 人工重裁 OK" % (key, f))
            else:
                print("!! %s mat_%d 失败" % (key, f))
        doc.close()
        with io.open(cfg["parsed"], "w", encoding="utf-8") as fp:
            json.dump(d, fp, ensure_ascii=False, indent=1)

    # opt 兜底图挂载（幂等）
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
                if q["options"].get(L) in ("(待校)", None):
                    q["options"][L] = "(见图)"
        if changed:
            with io.open(cfg["parsed"], "w", encoding="utf-8") as fp:
                json.dump(d, fp, ensure_ascii=False, indent=1)
    print("opt 挂载", n_opt, "张")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
