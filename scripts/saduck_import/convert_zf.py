# -*- coding: utf-8 -*-
import os as _os
_HOME = _os.environ.get("KG_HOME", _os.path.expanduser("~"))
def _p(*parts):
    return _os.path.join(_HOME, *parts)
"""zf_parsed.json -> 工作台题库格式 -> add-q 导入 -> build"""
import io
import json
import subprocess
import sys

TMP = _p("WorkBuddy", "2026-09-19-20-27-33", ".tmp", "gongkao")
SRC = TMP + r"\zf_parsed.json"
OUT = TMP + r"\题库数据_2022国考行政执法卷.json"
STORE = _p("Desktop", "考公工作台")
PY = _p(".workbuddy", "binaries", "python", "envs", "default", "Scripts", "python.exe")
LS = _p(".workbuddy", "skills", "kaogong-workbench", "scripts", "local_store.py")
PAPER = "2022国考行政执法卷"

PARTS = [(20, "常识判断"), (60, "言语理解与表达"), (70, "数量关系"),
         (110, "判断推理"), (130, "资料分析")]

# OCR 高频混淆字的安全修正表（只收确认不会误伤的词）
SAFE_FIX = [
    ("完法", "宪法"), ("罗辑", "逻辑"),
    ("友展", "发展"), ("友生", "发生"), ("友射", "发射"), ("友挥", "发挥"),
    ("友现", "发现"), ("友布", "发布"), ("友言", "发言"), ("友掘", "发掘"),
    ("人否", "能否"), ("人台", "5台"), ("人金", "一金"),
]


def fix(s):
    if not s:
        return s
    for a, b in SAFE_FIX:
        s = s.replace(a, b)
    return s


def part_of(n):
    for hi, name in PARTS:
        if n <= hi:
            return name
    return "资料分析"


def main():
    d = json.load(io.open(SRC, encoding="utf-8"))
    bank = []
    for n in range(1, 131):
        r = d[str(n)]
        bank.append({
            "pid": "%s-%d" % (PAPER, n),
            "paper": PAPER,
            "id": n,
            "part": part_of(n),
            "sub": "",
            "stem": fix(r["stem"]),
            "options": {L: fix(v) for L, v in r["options"].items()},
            "answer": r["answer"],
            "explain": fix(r["explain"]),
        })
    with io.open(OUT, "w", encoding="utf-8") as fp:
        json.dump(bank, fp, ensure_ascii=False, indent=1)
    print("转换完成:", OUT, "|", len(bank), "题")
    dist = {}
    for q in bank:
        dist[q["part"]] = dist.get(q["part"], 0) + 1
    print("板块分布:", dist)

    for step in (["add-q", "--json", OUT], ["build"]):
        cmd = [PY, LS] + step + ["--dir", STORE]
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        print("$ local_store", step[0])
        print((res.stdout or "").strip())
        if res.returncode != 0:
            print("STDERR:", (res.stderr or "").strip()[:600])
            sys.exit(1)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
