# -*- coding: utf-8 -*-
import os as _os
_HOME = _os.environ.get("KG_HOME", _os.path.expanduser("~"))
def _p(*parts):
    return _os.path.join(_HOME, *parts)
"""扫描 行测真题pdf 全部 PDF，生成录入清单 papers_list.json。"""
import io
import json
import os
import re
import sys

BASE = _p("Desktop", "行测真题pdf")
OUT = _p("WorkBuddy", "2026-09-19-20-27-33", ".tmp", "gongkao", "papers_list.json")

# 特殊目录 -> 省名（目录名即省名的直接用目录名）
DIR_ALIAS = {"国考": None, "广州市": "广州", "深圳市": "深圳"}


def parse_name(path, dname):
    fn = os.path.basename(path)
    m = re.match(r"^(\d{4})年?(.+?)$", fn)
    if not m:
        return None
    year = m.group(1)
    body = m.group(2)
    prov = DIR_ALIAS.get(dname, dname)
    is_gk = dname == "国考"
    # 类别提取
    cat = ""
    for pat in ("副省级", "地市级", "行政执法卷", "行政执法", "乡镇卷", "区级及以上卷",
                "乡镇", "县级 乡镇", "省市州级（A类）", "省级"):
        if pat in body:
            cat = pat
            break
    for pat in ("（A类）", "（B类）", "（C类）"):
        if pat in body:
            cat = pat.strip("（）")
            break
    if "选调" in body:
        cat = (cat + "选调") if cat else "选调"
    if "公安" in body or "公检法" in body or "监狱" in body or "法检" in body:
        cat = (cat + "公检法") if cat else "公检法"
    if "下半年" in body:
        cat = (cat + "下半年") if cat else "下半年"
    if "联考" in body:
        cat = (cat + "联考") if cat else "联考"
    if "兵团" in body:
        cat = (cat + "兵团") if cat else "兵团"
    if is_gk:
        paper = "%s国考%s" % (year, cat or "")
        prov_name = "国考"
    else:
        if prov in ("内蒙古", "黑龙江"):
            suffix = "区考" if prov == "内蒙古" else "省考"
        elif prov in ("上海", "北京", "江苏", "浙江", "山东", "广东", "深圳", "广州"):
            suffix = "市考" if prov in ("上海", "北京", "深圳", "广州") else "省考"
        else:
            suffix = "省考"
        paper = "%s%s%s%s" % (year, prov, suffix, cat)
        prov_name = prov
    if "(1)" in fn:
        paper += "-副本"
    return {"file": path, "paper": paper, "year": year, "prov": prov_name, "cat": cat}


def main():
    items, skipped = [], []
    used = set()
    for dname in sorted(os.listdir(BASE)):
        d = os.path.join(BASE, dname)
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            if not f.endswith(".pdf"):
                continue
            p = os.path.join(d, f)
            info = parse_name(p, dname)
            if info is None:
                skipped.append(f)
                continue
            # 重名消歧：《》内文字 -> 序号
            base = info["paper"]
            if base in used:
                mm = re.search(r"《(.+?)》", f)
                alt = base + (mm.group(1)[:10] if mm else "")
                info["paper"] = alt if alt not in used else base + "-2"
                if info["paper"] in used:
                    k = 2
                    while "%s-%d" % (base, k) in used:
                        k += 1
                    info["paper"] = "%s-%d" % (base, k)
            used.add(info["paper"])
            items.append(info)
    with io.open(OUT, "w", encoding="utf-8") as fp:
        json.dump(items, fp, ensure_ascii=False, indent=1)
    print("共 %d 份 PDF，未识别 %d" % (len(items), len(skipped)))
    for s in skipped:
        print("  跳过:", s)
    byprov = {}
    for it in items:
        byprov[it["prov"]] = byprov.get(it["prov"], 0) + 1
    for k in sorted(byprov):
        print("  %-6s %d 份" % (k, byprov[k]))
    # 重名 paper 检查
    names = {}
    dup = []
    for it in items:
        names.setdefault(it["paper"], []).append(os.path.basename(it["file"]))
    for k, v in names.items():
        if len(v) > 1:
            dup.append((k, v))
    print("重名 paper:", len(dup))
    for k, v in dup[:10]:
        print("  ", k, v)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
