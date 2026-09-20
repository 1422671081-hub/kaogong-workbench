# -*- coding: utf-8 -*-
import os as _os
_HOME = _os.environ.get("KG_HOME", _os.path.expanduser("~"))
def _p(*parts):
    return _os.path.join(_HOME, *parts)
"""对 zf_parsed.json 做最终人工修补（全部经原图目视核对）"""
import io
import json
import sys

F = _p("WorkBuddy", "2026-09-19-20-27-33", ".tmp", "gongkao", "zf_parsed.json")

PATCH = {
    "22": {"options": {"A": "敬而远之", "B": "不求甚解", "C": "不以为然", "D": "浅尝辄止"}},
    "32": {"options": {"A": "异军突起 推陈出新"}},
    "68": {"options": {"A": "50/63", "B": "125/126", "C": "25/63", "D": "125/252"}},
    "70": {"options": {"A": "3/4", "B": "8/11", "C": "11/15", "D": "225/256"}},
    "74": {"options": {"A": "(图形)", "B": "(图形)", "C": "(图形)", "D": "(图形)"}},
    "75": {"options": {"A": "(图形)", "B": "(图形)", "C": "(图形)", "D": "(图形)"}},
    "76": {"options": {"A": "(图形)", "B": "(图形)", "C": "(图形)", "D": "(图形)"}},
    "86": {"options": {
        "A": "(表格)2016~2020年某市税收情况：2016年1530、2017年1950、2018年2390、2019年3025、2020年3650（亿元）",
        "B": "(表格)2017~2020年某公司员工人数情况：2017年4459、2018年4925、2019年5012、2020年5347（人）",
        "C": "(表格)2021年1~5月某地区城镇私营单位就业人员月均工资：1月3530、2月3600、3月4150、4月3920、5月4300（元）",
        "D": "(表格)2020年某地区各季度电动汽车生产产量：一季度160、二季度182、三季度205、四季度217（万辆）"}},
    "111": {"options": {"D": "5"}},
}

d = json.load(io.open(F, encoding="utf-8"))
for q, p in PATCH.items():
    r = d[q]
    for k, v in p.items():
        if k == "options":
            r[k].update(v)
        else:
            r[k] = v

bad = []
for q, r in d.items():
    miss = [L for L in "ABCD" if not r["options"].get(L)]
    if miss or not r["answer"]:
        bad.append((q, miss, r["answer"]))
print("修补完成。仍缺:", bad or "无")
print("答案分布:", {L: sum(1 for r in d.values() if r["answer"] == L) for L in "ABCD"})
with io.open(F, "w", encoding="utf-8") as fp:
    json.dump(d, fp, ensure_ascii=False, indent=1)
print("已写回", F)
