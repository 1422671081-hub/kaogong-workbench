# -*- coding: utf-8 -*-
import os as _os
_HOME = _os.environ.get("KG_HOME", _os.path.expanduser("~"))
def _p(*parts):
    return _os.path.join(_HOME, *parts)
"""合并 12 套 bank -> add-q -> build；顺带给 2022 执法卷补判断推理 sub。"""
import io
import json
import subprocess
import sys

sys.path.insert(0, _p("WorkBuddy", "2026-09-19-20-27-33", ".tmp", "gongkao"))
from batch_lib import PAPERS, STORE, sub_of

PY = _p(".workbuddy", "binaries", "python", "envs", "default", "Scripts", "python.exe")
LS = _p(".workbuddy", "skills", "kaogong-workbench", "scripts", "local_store.py")
OUT = _p("WorkBuddy", "2026-09-19-20-27-33", ".tmp", "gongkao", "题库数据_2023-2026国考12套.json")


def main():
    all_q = []
    for key, cfg in PAPERS.items():
        d = json.load(io.open(cfg["parsed"], encoding="utf-8"))
        for q in d["bank"]:
            q.pop("figimg", None)
            if q["answer"] and not all(q["options"].get(L) for L in "ABCD"):
                for L in "ABCD":
                    if not q["options"].get(L):
                        q["options"][L] = "(待校)"
            all_q.append(q)
    with io.open(OUT, "w", encoding="utf-8") as fp:
        json.dump(all_q, fp, ensure_ascii=False, indent=1)
    print("合并", len(all_q), "题 ->", OUT)

    # 2022 执法卷 sub 回填
    qp = STORE + r"\questions.json"
    bank22 = json.load(io.open(qp, encoding="utf-8"))
    n_sub = 0
    for q in bank22:
        if q.get("paper") == "2022国考行政执法卷" and q.get("part") == "判断推理" and not q.get("sub"):
            if q["id"] in (71, 72, 73, 74, 75, 76):
                q["sub"] = "图形推理"
            else:
                q["sub"] = sub_of(q["stem"], q["options"])
            n_sub += 1
    with io.open(qp, "w", encoding="utf-8") as fp:
        json.dump(bank22, fp, ensure_ascii=False, indent=1)
    print("2022执法卷 sub 回填", n_sub, "题")

    for step in (["add-q", "--json", OUT], ["build"]):
        r = subprocess.run([PY, LS] + step + ["--dir", STORE],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        print("$ local_store", step[0])
        print((r.stdout or "").strip())
        if r.returncode:
            print(r.stderr[:500]); sys.exit(1)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
