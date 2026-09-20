---
name: kaogong-workbench
description: |
  考公工作台的题库管理助手。把整套试卷 PDF 录进题库、记录和查询错题、
  生成艾宾浩斯复习清单、汇总刷题打卡统计，并生成可离线使用的单文件刷题页。
  触发词：录题、录入试卷、把这份卷子录进去、报错题、第几题错了、今日复习、
  错题本、刷题统计、打卡统计、考公题库、考公工作台。
license: MIT
---

# 考公工作台

把整套试卷 PDF 变成一套可刷题、可管错题、可按遗忘曲线复习的工作台。

**本技能有两种运行模式，动手前必须先探测环境** —— 探测不清楚就做错方向，返工代价很大。

## 〇、环境探测（每次会话首次使用时做一次）

| 模式 | 判据 | 数据存哪 | 多设备同步 |
|---|---|---|---|
| **A · 云端模式** | 当前环境有 WorkBuddy 资料库能力 | 资料库三张结构化表 | 有 |
| **B · 本地模式** | 其它情形（别的 AI 客户端 / 没有资料库） | 本地 JSON 目录 | 无 |

**探测方法**：尝试调用 `library` 技能里的 database 脚本（例如列一下资料库位置，
或读一次表结构）。**能正常返回 → 模式 A；脚本不存在或报错 → 模式 B。**

探测不明时直接问用户一句：「你用的是 WorkBuddy 吗？有没有资料库功能？」

**硬要求：判定为模式 B 后，禁止再尝试任何云端接口。** 本地模式是完整可用的独立方案，
不是残废版；不要因为"同步不了"就让用户装 WorkBuddy，也不要把本地数据偷偷往云上推。

## 一、模式 A · 云端模式

数据存资料库三张结构化表，手机、电脑共用同一份数据。

### A1. 首次使用：先确认表，没有就建

检查本地配置文件 `config.json`（与本 SKILL.md 同级）：

- **有** `database_id.questions` → 直接用里面三个 ID，跳到 A2
- **没有** → 说明是本机首次使用，按下面建三张表，把返回的 `database_id` 写进 `config.json`：

```json
{
  "mode": "cloud",
  "space_id": "<目标空间 id，可省略，省略则落「我的文档」>",
  "database_id": {
    "questions": "<建表返回的 database_id>",
    "wrong":     "<建表返回的 database_id>",
    "checkin":   "<建表返回的 database_id>"
  }
}
```

建表用 `library` 技能的 `database/create_database.py --token-stdin --schema '<JSON>'`。
三张表的字段定义见本文件第三节，**字段名必须逐字照抄，不要翻译**。

### A2. 日常读写

一律走 `library` 技能的 database 脚本：

| 动作 | 脚本 |
|---|---|
| 查记录 | `query_database_record.py --token-stdin --database-id <id>` |
| 批量写入（≤100 条/次） | `batch_add_database_records.py --token-stdin --stdin` |
| 批量修改 | `batch_update_database_records.py --token-stdin --stdin` |
| 批量删除 | `batch_delete_database_records.py --token-stdin --stdin` |

**不要自己拼 HTTP 请求**，不要向用户索取 token / cookie。鉴权由宿主处理。

### A3. 配套网页

题库表 + 错题表 + 打卡表可被一个页面读取渲染。本技能**不附带**该页面。
用户想要的话，用 `library` 技能的 page 能力生成一个数据驱动页即可。

## 二、模式 B · 本地模式

数据落在本地目录，纯标准库、零第三方依赖，随时可离线用。

### B1. 初始化

```bash
python3 scripts/local_store.py init --dir ./kaogong-data
```

生成 `questions.json` / `wrong.json` / `checkin.json` / `img/` 四个位置。

### B2. 录题

```bash
python3 scripts/local_store.py add-q --dir ./kaogong-data --json new-questions.json
```

`--json` 指向一个题目数组（字段规范见第三节）。已在库的 `pid` 会被覆盖，新增的追加。
配图按文件名放进 `kaogong-data/img/`。写完后脚本会提示哪些图还没到位。

### B3. 错题与复习

```bash
# 记一道错题（错次 +1、复习阶段归 0、下次复习 = 明天）
python3 scripts/local_store.py wrong --dir ./kaogong-data --pid "2022国考副省级-76"

# 看今天该复习什么
python3 scripts/local_store.py due --dir ./kaogong-data

# 报告复习结果（--right 表示答对，推进一轮；不加则打回第 1 轮）
python3 scripts/local_store.py review --dir ./kaogong-data --pid "..." --right
```

### B4. 打卡与统计

```bash
python3 scripts/local_store.py checkin --dir ./kaogong-data --module 言语理解 \
    --done 10 --correct 8 --minutes 15

python3 scripts/local_store.py stats --dir ./kaogong-data
```

### B5. 生成单文件刷题页（本地模式的主要用途）

```bash
python3 scripts/local_store.py build --dir ./kaogong-data --out ./考公工作台.html
```

产出**一个自包含 HTML**：题库和图片（base64）全部内嵌，**双击即用，不需要服务器、
不需要联网、不需要带 img/ 目录**，可以随便发给别人。

页面自带：顺序刷 / 随机刷、五大模块两级分类、错题本、艾宾浩斯复习、打卡记录、图表统计。
刷题记录存在浏览器 `localStorage` 里。

> 单文件页的刷题记录只存在**打开它的那台设备**上，不会回写本地 JSON、也不跨设备同步。
> 要跨设备就用模式 A，或者把页面文件放网盘里。

## 三、题目字段规范（两种模式通用）

**字段名逐字照抄，不要翻译、不要加空格。**

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | 整数 | 题号 |
| `pid` | 文本 | 全局唯一 = 试卷 + "-" + 题号，如 `2022国考副省级-76` |
| `part` | 文本 | 五大模块之一：常识判断 / 言语理解 / 数量关系 / 判断推理 / 资料分析 |
| `sub` | 文本 | 仅判断推理用：图形推理 / 定义判断 / 类比推理 / 逻辑判断 |
| `stem` | 文本 | 题干 |
| `options` | 对象 | `{"A":"…","B":"…","C":"…","D":"…"}`；图形推理题填占位符「A 图」等 |
| `answer` | 文本 | 单个大写字母 A/B/C/D |
| `explain` | 文本 | 解析，忠于原卷解析版，不要润色 |
| `paper` | 文本 | 试卷名，如「2022国考副省级」 |
| `l2` / `l3` | 文本 | 二级 / 三级分类（言语理解、资料分析用得多） |
| `kp` | 文本 | 考点标签，如「判断推理·图形推理·面」；**不能由 l2·l3 推导**，有第三层细分 |
| `material` | 文本 | 材料题共用材料，最长约 1300 字 |
| `img` | 文本 | 材料图文件名（单张） |
| `imgs` | 数组 | 材料图文件名（多张） |
| `qimg` | 文本 | 题目配图文件名（图形推理、饼图选项等） |
| `fig` | 布尔 | 图形推理题填 `true`，页面会给它强制横滚 |

**云端模式的中文字段名**：题干 / 模块 / 子类 / 二级分类 / 三级考点 / 考点标签 /
选项A~D / 答案 / 解析 / 材料 / 材料图 / 题目图 / 图形推理题 / 试卷 / 题号 / pid。
错题表：pid / 题干 / 模块 / 题号 / 错误次数 / 复习阶段 / 下次复习 / 最近错误 / 来源 / 备注。
打卡表：日期 / 模块 / 题数 / 正确数 / 用时分钟 / 备注。

## 四、录题流程（PDF → 题库）

用户发来一份试卷 PDF（电子版，不是拍照）。

### 4.0 先检测文字层能不能用（必做，否则白干）

**不是所有 PDF 都能提取文字。** 不少机构（尤其考试培训类）会嵌入**自定义编码字体**做防复制，
`pdftotext` 和 `get_text()` 只会吐出乱码。

**检测方法**：提取第 1 页正文，数汉字占比。**汉字占比低于 30% 就是文字层不可用。**

典型症状：输出形如 `¢£¤¥¦§v%!"#$%&'(&¨©ª'!«`。按字体拆 span 会发现正文用的是
`FzBookMaker*`（方正书版）这类子集字体、`enc` 为空、无 ToUnicode 映射，
而唯一正常的字体（如 `SimSun + UniGB-UTF16-H`）只用在 `www.offcn.com` 水印上。
同类问题在 docx 里也存在（字符被编码成西文码位，靠字体字形"画"成中文，
表现为全篇几乎没有汉字、字体清单全是 Times New Roman / Lucida Sans Unicode 之类）。

**三种应对，按优先级：**

1. **找文字层正常的来源**。网上常有考生回忆版（华图、粉笔、金标尺等），
   有的站点直接提供文字层完好的 PDF，能省掉全部识图工作。
2. **渲染成图 + 识图**：`pdf_tools.py dump` 渲染后逐页看图。最准，但慢。
3. **渲染成图 + OCR**：`page.get_textpage_ocr(language='chi_sim', dpi=300, full=True, tessdata=...)`。
   中文包可从 `cdn.jsdelivr.net/gh/tesseract-ocr/tessdata_fast@main/chi_sim.traineddata` 取（约 2.4 MB，jsdelivr 可直连）。
   速度约 1 秒/页，**字符准确率约 95%，但序号 ①②③④⑤ 几乎必错、形近字频出
   （党→觉、血→所、入→和）、选项标点也会丢（`A.`→`A2`）**。
   → **只能当誊稿初稿省打字力气，最终必须以原图核对。**

> ⚠️ **用网上回忆版的陷阱**：回忆版的**选项顺序经常与原卷不同**，答案字母会随之错位。
> 例如原卷 `A.甲 B.乙 C.丙` 答案 C，回忆版可能排成 `A.甲 B.丙 C.乙`，答案就变成了 B。
> 引用它的**文字内容**没问题，但**答案必须回到原卷核对，绝不能照抄回忆版的答案字母**。

### 4.1 PDF 处理环境

优先用自带的 `scripts/pdf_tools.py`，依赖 **pymupdf**（`pip install pymupdf`，纯 Python 包）。
装不了就改用系统 poppler，两条路效果等价：

```bash
# 有 pymupdf
python3 scripts/pdf_tools.py text  "<原卷.pdf>" --page 29 --head 3
python3 scripts/pdf_tools.py dump  "<原卷.pdf>" --pages 1-40 --dpi 150 --out ./work
python3 scripts/pdf_tools.py crop  "<原卷.pdf>" --page 31 --box 120,880,1180,1180 --out ./q-76.png

# 无 pymupdf
pdftotext -f 29 -l 29 -layout "<原卷.pdf>" - | head -40
pdftoppm -f 29 -l 35 -r 150 -png "<原卷.pdf>" ./work/page
python3 -c "from PIL import Image; Image.open('./work/page-31.png').crop((120,880,1180,1180)).save('./q-76.png')"
```

> `pdftoppm` 生成的页码不补零，`page-3.png` 和 `page-30.png` 会混在一起，认准文件名。

### 4.2 先确认物理页与卷面页码的偏移

**PDF 物理页 ≠ 卷面页码**，必须先试读几页确认，不要假设第 1 页就是第 1 题。
（2022 国考副省级实测偏移：卷面第 25 页 = 物理第 29 页，卷面第 30 页 = 物理第 35 页）

### 4.3 结构化的三条硬规则

**① 填空题的横线只能来自原卷排版，不能靠语感猜。**
横线数量用解析里「第 N 空」交叉验证，位置必须回原卷看排版。
统一用 8 个下划线 `________` 作填空标记。

**② 中文标点统一半角 + 1 个空格。** 全角逗号、冒号清零。

**③ 答案和解析忠于原卷解析版**，不要自行改写润色，也不要凭猜测补。

### 4.4 配图处理

- **图形推理题**：题干是固定表述，选项填「A 图」等占位符，四个图形通常排在一张横图里 → `qimg`，并设 `fig: true`
- **资料分析材料图**：材料文字进 `material`，图表进 `img`（多张则 `imgs`）
- **饼图 / 表格类选项**：进 `qimg`

裁图按**坐标**裁（图形题在页面上位置无规律，按比例框选会错）：

```bash
python3 scripts/pdf_tools.py crop "<原卷.pdf>" --page 31 --dpi 150 --box x0,y0,x1,y1 --out ./q-76.png
```

**裁完必须肉眼扫一遍图片底部**，确认没有把下一题的题干带进来（这是最容易犯的错）。

配图放进 `kaogong-data/img/`（本地模式），文件名与 `img` / `qimg` / `imgs` 字段一致。
云端模式则先转托管直链再写图片字段（`library` 技能的 `manage/upload_image.py`），
**不要 base64 内嵌**。

### 4.5 录完必须回读校验

不要凭"提交成功"就宣布完成。至少核对：

```
记录数 · 题号是否连续无缺口 · 有无重复 pid · 各模块题数 · 含图题数 · 图形推理题数
```

对不上就说清楚差在哪。

## 五、错题与复习规则（两种模式一致）

- 错题按 `pid` 唯一，**一题永远只占一行**；同题再错是累加次数，不是新增
- 复习间隔：**1 / 2 / 4 / 7 / 15 / 30 天**，共 6 轮
- 答对推进一轮；走完 6 轮标记毕业（本地模式记 `stage=99`）
- 复习时又答错 → **打回第 1 轮**，明天再来
- 主动重做答对的题 → 判定已掌握，移出错题本

## 六、硬规则

1. **先探测环境再动手**（见第〇节）；模式 B 下禁止调用任何云端接口。
2. **不要自己拼 HTTP 请求**，不要向用户索要 token / cookie，不要伪造 ID。
3. **字段名逐字照抄**第三节，不翻译、不加空格。
4. 云端模式批量写入**单次不超过 100 条**，必须走 `--stdin`，子进程设 UTF-8 编码。
5. 涉及**删除**（删题、清错题、清空）必须先向用户确认，说明影响多少条。
6. 录完**必须回读校验**，如实报告核对结果。
7. 数据来源只认**原卷解析版**，不凭猜测补答案或解析。
