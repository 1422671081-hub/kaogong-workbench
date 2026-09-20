# -*- coding: utf-8 -*-
import os as _os
_HOME = _os.environ.get("KG_HOME", _os.path.expanduser("~"))
def _p(*parts):
    return _os.path.join(_HOME, *parts)
"""给执法卷题目补图表：图形推理整题图、资料分析材料图、文字材料。"""
import io
import json
import subprocess
import sys

F = _p("WorkBuddy", "2026-09-19-20-27-33", ".tmp", "gongkao", "题库数据_2022国考行政执法卷.json")
STORE = _p("Desktop", "考公工作台")
PY = _p(".workbuddy", "binaries", "python", "envs", "default", "Scripts", "python.exe")
LS = _p(".workbuddy", "skills", "kaogong-workbench", "scripts", "local_store.py")

MAT_106 = ("某超市从前到后整齐排列着7排货架，放置着文具、零食、调料、日用品、酒、粮油和饮料7类商品，"
           "每类商品占据一排。已知：\n（1）酒类排在调料类之前；\n（2）文具类和调料类中间隔着3排；\n"
           "（3）粮油类在零食类之后，中间隔着2排；\n（4）日用品类紧挨在文具类前一排或者后一排。")

MAT_116 = ("2020年12月，全国“12369环保举报联网管理平台”共接到环保举报31156件，环比下降23.2%，"
           "同比下降10.3%，其中，受理量23792件，较11月减少6316件；因举报线索不详或不属于生态环境部门"
           "职责范围而未受理2364件，较11月减少3119件。")

MAT_126 = ("2021年1-5月，全国共破获电信网络诈骗案件11.4万起，打掉犯罪团伙1.4万个，抓获犯罪嫌疑人15.4万名，"
           "同比分别上升60.4%、80.6%和146.5%。2021年5月，全国共立电信网络诈骗案件8.46万起，与上月相比下降14.3%。\n"
           "2021年1-5月，全国拦截诈骗电话6.1亿次，拦截诈骗短信9.1亿条，封堵诈骗网址82.1万个。1-5月公安部日均下发预警指令5.2万条。\n"
           "2021年1-5月，全国成功劝阻771万名群众免于受骗，紧急止付涉案资金2654亿元，为群众挽回经济损失991亿元。\n"
           "2021年1-5月，全国公安机关捣毁境内诈骗窝点6500余个，共破获被骗百万元以上案件881起，同比上升160.5%，"
           "先后组织20次集中收网行动，抓获犯罪嫌疑人2421名，打掉技术开发平台、网络引流推广、虚拟货币洗钱等团伙380余个。\n"
           "2020年10月至2021年5月，全国公安机关会同检察、法院、通讯、金融等部门，共打掉“两卡”违法犯罪团伙1.5万个，"
           "缴获涉诈电话卡373.3万张，银行卡56.6万张，惩戒“两卡”失信人员17.3万名，整治违规行业网点机构1.8万家。")


def main():
    bank = json.load(io.open(F, encoding="utf-8"))
    by_id = {q["id"]: q for q in bank}

    for n in range(71, 77):                      # 图形推理：整题图
        q = by_id[n]
        q["qimg"] = "zf_fig_%d.png" % n
        q["fig"] = True
        q["options"] = {L: "(见图)" for L in "ABCD"}

    by_id[86]["imgs"] = ["zf_q86a.png", "zf_q86b.png"]

    for n in range(106, 111):                    # 货架排队：文字材料
        by_id[n]["material"] = MAT_106

    for n in range(111, 116):                    # 食品抽检表
        by_id[n]["imgs"] = ["zf_mat_111.png"]

    for n in range(116, 121):                    # 环保举报：文字+表+柱状图
        by_id[n]["imgs"] = ["zf_mat_116a.png", "zf_mat_116b.png"]
        by_id[n]["material"] = MAT_116
    by_id[120]["qimg"] = "zf_q120.png"           # 120 题干折线图

    for n in range(121, 126):                    # IC封装图
        by_id[n]["imgs"] = ["zf_mat_121.png"]

    for n in range(126, 131):                    # 诈骗：纯文字材料
        by_id[n]["material"] = MAT_126

    with io.open(F, "w", encoding="utf-8") as fp:
        json.dump(bank, fp, ensure_ascii=False, indent=1)
    n_img = sum(1 for q in bank if q.get("qimg") or q.get("imgs"))
    n_mat = sum(1 for q in bank if q.get("material"))
    print("已更新：配图 %d 题，文字材料 %d 题" % (n_img, n_mat))

    for step in (["add-q", "--json", F], ["build"]):
        cmd = [PY, LS] + step + ["--dir", STORE]
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        print("$ local_store", step[0])
        print((r.stdout or "").strip())
        if r.returncode:
            print(r.stderr[:400]); sys.exit(1)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
