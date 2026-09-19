# 公考题库助手 · gongkao-tiku

一个 AI Agent 技能：**把整套试卷 PDF 变成一套可刷题、可管错题、能按遗忘曲线复习的工作台。**

适用于任何支持 Skill / Agent Skills 规范的 AI 客户端（WorkBuddy、Claude Code 等）。

---

## 它能做什么

- **录题**：丢一份试卷 PDF 进来，自动提取题目（含图形推理、资料分析图表），结构化入库
- **刷题**：生成一个**自包含单文件 HTML**，双击就能刷，图片全部内嵌，不需要服务器、不需要联网
- **错题本**：按题目去重，同一道题错多次只记一次，累计错误次数
- **艾宾浩斯复习**：按 1 / 2 / 4 / 7 / 15 / 30 天安排 6 轮复习，答对推进、答错打回
- **打卡统计**：每日每模块题量、正确率、用时，带图表

## 两种运行模式

技能会**自动探测运行环境**，选择合适的数据存储方式：

| 模式 | 什么环境下用 | 数据存哪 | 多设备同步 |
|---|---|---|---|
| **A · 云端模式** | 有 WorkBuddy 资料库 | 资料库三张结构化表 | ✅ 有 |
| **B · 本地模式** | 其它 AI 客户端 | 本地 JSON 目录 | ❌ 无 |

**本地模式是完整可用的独立方案**，不是残废版 —— 录题、错题、复习、统计、生成刷题页
全都支持，只是数据不跨设备同步。

---

## 安装

### WorkBuddy

「设置 → 技能管理 → 导入本地技能包」，选择本仓库打包出的 zip / `.skill` 文件。

### Claude Code（或其它支持 Agent Skills 的客户端）

把本目录放到客户端的 skills 目录下即可，例如：

```bash
git clone https://github.com/1422671081-hub/gongkao-tiku.git ~/.claude/skills/gongkao-tiku
```

---

## 快速上手（本地模式）

```bash
# 1. 初始化数据目录
python3 scripts/local_store.py init --dir ./gongkao-data

# 2. 录入题目（new-questions.json 是一个题目数组，字段规范见 SKILL.md 第三节）
python3 scripts/local_store.py add-q --dir ./gongkao-data --json new-questions.json

# 3. 记错题
python3 scripts/local_store.py wrong --dir ./gongkao-data --pid "2022国考副省级-76"

# 4. 看今天该复习什么
python3 scripts/local_store.py due --dir ./gongkao-data

# 5. 打今天的卡
python3 scripts/local_store.py checkin --dir ./gongkao-data \
    --module 言语理解 --done 10 --correct 8 --minutes 15

# 6. 生成单文件刷题页
python3 scripts/local_store.py build --dir ./gongkao-data --out ./公考工作台.html
```

生成出来的 `公考工作台.html` **双击即用**，也可以直接发给朋友。

> 更省事的用法是把 PDF 直接丢给你的 AI 助手，说一句「录这套卷子」，让它读 SKILL.md 自己走流程。

---

## PDF 处理依赖

提取题目文字和裁切配图需要以下任一套环境：

| 方案 | 依赖 | 说明 |
|---|---|---|
| 推荐 | `pip install pymupdf` | 纯 Python 包，跨平台，可移植性最好 |
| 备选 | `poppler-utils` + `Pillow` | 用系统的 `pdftotext` / `pdftoppm` |

不装也能用 —— 技能会走备选路径。

---

## 目录结构

```
gongkao-tiku/
├── SKILL.md                 技能定义与完整工作流
├── scripts/
│   ├── pdf_tools.py         PDF 提字 / 渲染 / 裁切
│   └── local_store.py       本地模式数据管理与单文件页生成（纯标准库）
├── assets/
│   └── template.html        刷题页模板（构建时注入题库与图片）
└── config.json              云端模式的表 ID 配置（首次使用时生成，已在 .gitignore 中）
```

---

## 数据文件格式（本地模式）

`questions.json` —— 题目数组，一题一个对象，关键字段：

```json
{
  "id": 76,
  "pid": "2022国考副省级-76",
  "part": "判断推理",
  "sub": "图形推理",
  "stem": "从所给的四个选项中，选择最合适的一个填入问号处，使之呈现一定的规律性：",
  "options": { "A": "A 图", "B": "B 图", "C": "C 图", "D": "D 图" },
  "answer": "C",
  "explain": "……",
  "paper": "2022国考副省级",
  "kp": "判断推理·图形推理·面",
  "qimg": "q-76.png",
  "fig": true
}
```

`wrong.json` —— `{ pid: { times, stage, next, lastAt, note } }`

`checkin.json` —— `{ "YYYY-MM-DD": { modules: { 模块名: { done, correct, minutes } }, note } }`

配图放在 `gongkao-data/img/`，文件名与题目里的 `img` / `qimg` / `imgs` 字段一致。

---

## 许可

MIT
