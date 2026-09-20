# -*- coding: utf-8 -*-
import os as _os
_HOME = _os.environ.get("KG_HOME", _os.path.expanduser("~"))
def _p(*parts):
    return _os.path.join(_HOME, *parts)
"""人工修补落地：no_opts 图形题 -> 整题图；文字题转录；补答案。"""
import io
import json
import os
import sys

import fitz

sys.path.insert(0, _p("WorkBuddy", "2026-09-19-20-27-33", ".tmp", "gongkao"))
from batch_lib import PAPERS, IMGDIR, crop, stack_save

# no_opts 图形选项题：人工读图确认的答案
PIC_ANS = {
    ("2023地市级", 125): "C", ("2023地市级", 128): "B",
    ("2023副省级", 125): "A",
    ("2023行政执法", 115): "A", ("2023行政执法", 125): "C",
    ("2024行政执法", 84): "A",
    ("2025地市级", 68): "A", ("2025地市级", 126): "A",
    ("2025副省级", 125): "D", ("2025副省级", 130): "B",
    ("2025行政执法", 90): "D", ("2025行政执法", 125): "B",
    ("2026地市级", 115): "D", ("2026地市级", 128): "B",
    ("2026副省级", 133): "B", ("2026行政执法", 115): "D",
}

T93 = {
    "stem": "动作预期是指运动员在比赛过程中，根据已有信息，对即将发生的动作结果进行预测的过程。"
            "在这一过程中，运动员主要依赖两类信息：运动学信息和情境先验信息。运动学信息包括对手的动作、"
            "器材的运动轨迹或队员之间的相对位置，情境先验信息则涉及比赛情境中事件发生的概率。"
            "根据上述定义，下列不涉及上述任何一种信息的是：",
    "options": {
        "A": "篮球队员甲在双方比分紧咬的情况下，基于对手今日比赛罚篮命中率不高，在对手投篮时选择直接犯规",
        "B": "网球运动员乙知道对手在比赛前有一系列习惯性动作，包括整理球衣、球裤、头发等，暗自提醒自己不要被其干扰",
        "C": "羽毛球双打运动员丙发现对方准备接发球的球员位置稍微靠前，可能来不及转身或后退接球，便发了个后场球",
        "D": "乒乓球运动员丁发现对方发过来的球位置较低、速度较慢，极有可能擦网变线，便没有后退，向前伸拍做好接球准备"},
    "answer": "B", "sub": "定义判断",
}
T100 = {
    "stem": "缄口不言 对于 （ ） 相当于 （ ） 对于 虚怀若谷",
    "options": {"A": "三缄其口；大智若愚", "B": "畅所欲言；放荡不羁",
                "C": "守口如瓶；礼贤下士", "D": "口若悬河；矜功伐善"},
    "answer": "D", "part": "判断推理", "sub": "类比推理",
}


def main():
    for key, cfg in PAPERS.items():
        d = json.load(io.open(cfg["parsed"], encoding="utf-8"))
        bank = {q["id"]: q for q in d["bank"]}
        doc = None
        changed = False
        for r in d["repairs"]:
            if r.get("type") != "no_opts":
                continue
            qno = r["q"]
            ans = PIC_ANS.get((key, qno))
            sp = r["span"]
            if ans is None:
                continue
            if doc is None:
                doc = fitz.open(cfg["pdf"])
            fn = "zf2_%s_blk_%d.png" % (key, qno)
            parts = []
            p0, y_lo, p1, y_hi = sp["p"], sp["y0"], sp["p1"], sp["y1"]
            if p0 == p1:
                parts = [(p0, y_lo, y_hi)]
            else:
                parts = [(p0, y_lo, 806)] + [(p, 44, 806) for p in range(p0 + 1, p1)] + \
                        [(p1, 44, y_hi)]
            ims = [crop(doc, p, a, b) for p, a, b in parts]
            if stack_save(ims, os.path.join(IMGDIR, fn)):
                q = bank.get(qno)
                if q is None:                       # no_opts 题原本不在 bank
                    q = {"pid": "%s-%d" % (cfg["paper"], qno), "paper": cfg["paper"],
                         "id": qno, "part": "资料分析", "sub": "", "stem": "(见图)",
                         "options": {L: "(见图)" for L in "ABCD"}, "answer": ans,
                         "explain": "", "qimg": fn, "fig": True}
                    d["bank"].append(q)
                else:
                    q["qimg"] = fn; q["fig"] = True; q["answer"] = ans
                    q["options"] = {L: "(见图)" for L in "ABCD"}
                changed = True
                print("%s 题%d -> 图片题 ans=%s" % (key, qno, ans))
        # 特例：2026执法 93 文字题
        if key == "2026行政执法":
            q = bank.get(93)
            if q is None:
                q = {"pid": "%s-93" % cfg["paper"], "paper": cfg["paper"], "id": 93,
                     "part": "判断推理", "sub": T93["sub"], "stem": T93["stem"],
                     "options": T93["options"], "answer": T93["answer"], "explain": ""}
                d["bank"].append(q); changed = True
                print(key, "题93 文字转录(新建) ans=B")
            elif not q["options"].get("A"):
                q.update({"stem": T93["stem"], "options": T93["options"],
                          "answer": T93["answer"], "sub": T93["sub"]})
                changed = True
                print(key, "题93 文字转录 ans=B")
        if key == "2025行政执法":
            q = bank.get(73)
            if q is not None and not q["answer"]:
                q["answer"] = "A"; changed = True
                print(key, "题73 补答案 A")
        if key == "2023地市级":
            if 100 not in bank:
                q = {"pid": "%s-100" % cfg["paper"], "paper": cfg["paper"], "id": 100,
                     "part": T100["part"], "sub": T100["sub"], "stem": T100["stem"],
                     "options": T100["options"], "answer": T100["answer"], "explain": ""}
                d["bank"].append(q); changed = True
                print(key, "题100 文字转录 ans=D")
        if doc:
            doc.close()
        if changed:
            d["bank"].sort(key=lambda q: q["id"])
            with io.open(cfg["parsed"], "w", encoding="utf-8") as fp:
                json.dump(d, fp, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
