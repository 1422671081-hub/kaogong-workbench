# -*- coding: utf-8 -*-
import os as _os
_HOME = _os.environ.get("KG_HOME", _os.path.expanduser("~"))
def _p(*parts):
    return _os.path.join(_HOME, *parts)
"""全量批量录入 300+ 份省考卷（文字层版式）。断点续跑：parsed 已存在则跳过。"""
import io
import json
import os
import re
import sys

import fitz
from PIL import Image

sys.path.insert(0, _p("WorkBuddy", "2026-09-19-20-27-33", ".tmp", "gongkao"))
from batch_lib import IMGDIR, crop, stack_save

WORK = _p("WorkBuddy", "2026-09-19-20-27-33", ".tmp", "gongkao")
BATCHDIR = os.path.join(WORK, "prov")
STORE = _p("Desktop", "考公工作台")
DPI = 200
TOTAL_DEFAULT = 130

QNO = re.compile(r"^(\d{1,3})\s*[.、．]?\s*(\S.*)$")
OPT = re.compile(r"^([A-D])[.、]\s*(\S.*)$")
ANS = re.compile(r"【答案】\s*([A-D])")
SECTION = re.compile(r"^[一二三四五六七八九十]+、")
PAGEHEAD = re.compile(r"全部题目-常规|公务员录用考试《行测》|国家《行测》题")

SEC2PART = [("常识", "常识判断"), ("言语", "言语理解"), ("数量", "数量关系"),
            ("判断", "判断推理"), ("资料", "资料分析")]


def part_from(section):
    for k, v in SEC2PART:
        if k in (section or ""):
            return v
    return ""


def norm(s):
    return re.sub(r"[\s，。；：、“”‘’()（）·]", "", s or "")


def sub_of(stem):
    if re.search(r"规律性|截面|展开图|立体图形|折纸|纸盒|折叠", stem):
        return "图形推理"
    if re.search(r"根据上述定义|下列属于|不符合这一定义|定义的关键词", stem):
        return "定义判断"
    if len(stem) <= 16 and "：" in stem:
        return "类比推理"
    return "逻辑判断"


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


def build_lines(doc):
    out = []
    for pno in range(doc.page_count):
        dd = doc[pno].get_text("dict")
        for b in dd.get("blocks", []):
            if b.get("type") != 0:
                continue
            for l in b.get("lines", []):
                t = "".join(s.get("text", "") for s in l.get("spans", "")).strip()
                if not t or PAGEHEAD.search(t):
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
        mrows.append({"p": g[0]["p"], "y0": g[0]["y0"], "x0": g[0]["x0"],
                      "t": re.sub(r"\s+", " ", t).strip()})
    # 过滤页码
    return [r for r in mrows if not (re.fullmatch(r"\d{1,2}", r["t"]) and r["x0"] > 500)]


def parse_paper(lines):
    ans_start = next((k for k, r in enumerate(lines) if "【答案】" in r["t"]), None)
    if ans_start is None:
        return None, "找不到解析区"
    sec_positions = [(k, r["t"]) for k, r in enumerate(lines) if SECTION.match(r["t"])]

    def section_at(idx):
        name = ""
        for k, t in sec_positions:
            if k < idx:
                name = t
            else:
                break
        return name

    result, cur, stem_parts, opts, cur_opt, section = {}, None, [], {}, None, ""
    order = []
    for ri, r in enumerate(lines[:ans_start]):
        t = r["t"]
        if SECTION.match(t) or t.startswith("根据题目要求") or t.startswith("注："):
            continue
        m = QNO.match(t)
        mo = OPT.match(t)
        if m and int(m.group(1)) == (cur or 0) + 1 and r["x0"] < 60:
            if cur:
                result[cur] = {"stem": "".join(stem_parts).strip(), "options": opts,
                               "section": section}
                order.append(cur)
            cur = int(m.group(1)); stem_parts = [m.group(2)]; opts = {}; cur_opt = None
            section = part_from(section_at(ri))
            continue
        if mo and cur:
            cur_opt = mo.group(1)
            opts[cur_opt] = mo.group(2).strip()
            continue
        if cur:
            if cur_opt and opts.get(cur_opt):
                opts[cur_opt] = (opts[cur_opt] + t).strip()
            else:
                stem_parts.append(t)
    if cur:
        result[cur] = {"stem": "".join(stem_parts).strip(), "options": opts,
                       "section": section}
        order.append(cur)
    if not result:
        return None, "题目区无题"

    # 解析区
    expl, ans_map, cur_no = {}, {}, None
    for r in lines[ans_start:]:
        t = r["t"]
        m = QNO.match(t)
        ma = ANS.search(t)
        if m and int(m.group(1)) == (cur_no or 0) + 1 and r["x0"] < 60 and len(t) < 12:
            cur_no = int(m.group(1))
            if ma:
                ans_map[cur_no] = ma.group(1)
            continue
        if ma:
            nxt = (cur_no + 1) if cur_no else 1
            ans_map[nxt] = ma.group(1)
            cur_no = nxt
            continue
        if cur_no and not SECTION.match(t):
            expl.setdefault(cur_no, []).append(t)

    total = max(result)
    missing = [n for n in range(1, total + 1) if n not in result]
    for n in range(1, total + 1):
        q = result.get(n, {"stem": "", "options": {}, "section": ""})
        ex = "".join(expl.get(n, []))
        result[n] = {"id": n, "stem": q["stem"], "options": q["options"],
                     "answer": ans_map.get(n, ""), "explain": ex,
                     "section": q.get("section", ""), "part": q.get("section", "")}
    # section 记录修正：用题目区解析时各题的 section
    return {"result": result, "total": total, "missing": missing, "order": order}, None


def process(item, doc):
    lines = build_lines(doc)
    parsed, err = parse_paper(lines)
    if err:
        return None, err
    result, total = parsed["result"], parsed["total"]
    # part 校正：逐题从 section 拿（parse_paper 里 section 是 part_from 后的值，但
    # result[n]["part"] 在 parse_paper 内没写——这里从 section_at 无法拿，改用近似：
    # result[n]["part"] 由 parse_paper 写入 section 位置——检查
    bank = []
    for n in range(1, total + 1):
        q = result[str(n)] if str(n) in result else result[n]
        bank.append(q)
    return {"result": {str(k): v for k, v in result.items()}, "total": total,
            "missing": parsed["missing"], "order": parsed["order"]}, None


def main():
    items = json.load(io.open(os.path.join(WORK, "papers_list.json"), encoding="utf-8"))
    store = json.load(io.open(os.path.join(STORE, "questions.json"), encoding="utf-8"))
    have_papers = {q.get("paper") for q in store}
    todo = [it for it in items if it["paper"] not in have_papers]
    print("待录 %d / 共 %d 份" % (len(todo), len(items)))
    os.makedirs(BATCHDIR, exist_ok=True)

    done = fail = 0
    for i, it in enumerate(todo):
        pj = os.path.join(BATCHDIR, it["paper"] + ".json")
        if os.path.exists(pj):
            done += 1
            continue
        try:
            doc = fitz.open(it["file"])
            parsed, err = process(it, doc)
            doc.close()
            if err:
                fail += 1
                print("!! %s: %s" % (it["paper"], err))
                json.dump({"paper": it["paper"], "error": err},
                          io.open(pj, "w", encoding="utf-8"), ensure_ascii=False)
                continue
            parsed["paper"] = it["paper"]
            parsed["file"] = it["file"]
            parsed["prov"] = it["prov"]
            with io.open(pj, "w", encoding="utf-8") as fp:
                json.dump(parsed, fp, ensure_ascii=False)
            done += 1
            dist = {}
            for q in parsed["result"].values():
                dist[q["answer"]] = dist.get(q["answer"], 0) + 1
            print("[%d/%d] %s %d 题 缺号%s 分布%s" % (
                i + 1, len(todo), it["paper"], parsed["total"],
                parsed["missing"] or "无", dist))
        except Exception as e:
            fail += 1
            print("!! %s 异常: %s" % (it["paper"], str(e)[:120]))
            json.dump({"paper": it["paper"], "error": str(e)[:200]},
                      io.open(pj, "w", encoding="utf-8"), ensure_ascii=False)
    print("解析轮完成: 成功 %d 失败 %d" % (done, fail))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
