# AI Quant CLI

> 配套课程：AI 业务流架构师 · 第 18 节《AI Quant CLI 量化投研系统开发》

把一份 A 股年报 PDF，自动解析三张合并报表 → 由 **Claude Code 亲自**做财务风险研判与三表勾稽 → 出图 → 汇编成一份浏览器可直接打开的 HTML 投研报告。从一个**空目录**起步、先设计后施工造出来的一套**可复用、可重跑**的本地系统。

```
年报 PDF（按需检索：两百多页只取三张合并报表）
  ↓ L1 解析（pdfplumber 定位合并三表 + 会计恒等式自检）
data/parsed/financials.json
  ├─→ L2 出图（matplotlib，处理中文字体）→ build/figures/*.png
  └─→ L4 研判（Claude Code 亲自做，不是脚本）→ analysis/findings_<代码>.json
  ↓ L3 报告（fan-in 汇编单页 HTML）
reports/report_<代码>_<期>_<时间戳>.html
```

> 设计内核：**财务分析判断由 Claude Code 直接做，代码不调用大模型 API**——智能在它的 agent 循环里，不在某个 API 调用里。Python 脚本只做确定性工作（解析 PDF、出图、汇编 HTML）。详见 [CLAUDE.md](CLAUDE.md)。

## 与课程的关系

本项目是第 18 节的实战代码，服务于课程的三个核心留存物：

| 留存物 | 在本项目中的体现 |
|---|---|
| **先设计后施工** | 空目录起步，先让 Claude Code 出分层架构蓝图、你 review，再逐层施工；设计与踩坑修法固化进 `CLAUDE.md`，下次对话一上来就懂 |
| **智能在循环里，不在 API 调用里** | 财务风险研判（L4）由 Claude Code 亲自产出、可追问可解释；Python 只做确定性工作，全程不调大模型 API |
| **按需检索 + 三表勾稽** | 两百多页年报只取三张合并报表，不通读；用资产负债 / 利润 / 现金流互相印证，挖出单看一张表发现不了的风险 |

## 前置条件

| 条件 | 说明 |
|---|---|
| Claude Code 已装好并可对话 | 驱动它的模型用 Opus 4.8：Claude 订阅 `/login`，或 AI 中转站配 `ANTHROPIC_BASE_URL` / `ANTHROPIC_AUTH_TOKEN` |
| Python 3.10+ 与 pip | `python3 --version` 能正常输出 |
| 一份 A 股年报 PDF | 仓库已附宁德时代 / 比亚迪两份样例（`data/`），开箱即用；换标的见 [data/README.md](data/README.md) |

## 快速开始

```bash
cd ai-quant-cli
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple   # 国内源更快

python scripts/run_pipeline.py        # 一键端到端：解析 → 出图 → L4 闸门 → 报告（默认用宁德年报）
```

报告出在 `reports/`，文件名 `report_<股票代码>_<报告期>_<时间戳>.html`——**多次跑、多家公司都不覆盖**，历史留痕。跑通一键端到端你会看到本节的成品；但真正的学习在「从零自己造一遍」（见下）。

> 一键编排在进 L3 报告前会做 **L4 研判闸门**：研判结果（`analysis/findings_<代码>.json`）由分析者人工产出，缺失即报错停下、不静默出半成品。换新标的需先有它对应的 findings。

## 从零自己造一遍（推荐——这就是课上做的）

本节的重点不是跑现成代码，是从空目录把这套系统造出来。**在你自己的另一个空目录里做，不要在本仓库的 `ai-quant-cli/` 里做**——这里的 `src/` 是做好的参考答案。两种练法：

- **一步步练（推荐）**：照 [lesson18-lab.md](lesson18-lab.md) 的 prompt 一条条发给 Claude Code。
- **省事**：把本仓库的 [BUILD_PLAN.md](BUILD_PLAN.md)（6 阶段 goal-only 构建计划）拷进你的空目录，启动 Claude Code（**Auto 模式**），发「读 BUILD_PLAN.md，一步步把系统做出来，每阶段停一下」让它自己跑。

建完，拿本仓库 `src/` + `CLAUDE.md` 当参考答案对照你和它差在哪。

## 核心模块

| 模块 | 职责 |
|---|---|
| `src/ai_quant/parsing/extract.py` | L1 解析：按编号锚点定位**合并**三表，抽期末 / 期初科目 |
| `src/ai_quant/parsing/checks.py` | 会计恒等式自检（资产 = 负债 + 所有者权益） |
| `src/ai_quant/viz/charts.py` | L2 出图：读结构化数据渲染图，处理中文字体与负号 |
| `src/ai_quant/report/build.py` | L3 报告：fan-in 汇编单页 HTML（Jinja2） |
| `src/ai_quant/pipeline/run.py` | L5 编排：一键重跑，含 L4 研判闸门检查 |
| `src/ai_quant/common.py` | 科目别名表（统一不同公司的科目命名差异）+ JSON / 路径通用函数 |
| `scripts/*.py` | 各层 CLI 入口：`parse_report` / `make_figures` / `build_report` / `run_pipeline` |

> L4 研判不是代码——是 Claude Code 读 `financials.json` 后亲自产出 `analysis/findings_<代码>.json`，每条结论挂数据依据（指向具体报表 + 科目 + 期间）。

## 架构（DAG，不是直线流水线）

唯一硬约束：**L1 最先、L3 最后**。中间 L2 出图与 L4 研判互不依赖、可并行。每层只依赖上游落盘的 JSON 文件，不互相 import 业务逻辑——任意一层都能单独重跑。完整数据契约见 [CLAUDE.md](CLAUDE.md)。

## 完成标准

一次完整成功必须同时满足：

1. `data/parsed/financials.json` 已生成，会计恒等式自检通过（`balance_identity.ok = true`）
2. `analysis/findings_<代码>.json` 存在，每条风险 / 勾稽结论都挂了数据依据
3. `build/figures/*.png` 已生成，图中中文与负号显示正常（不是方框）
4. `reports/report_<代码>_<期>_<时间戳>.html` 已生成，浏览器打开排版正常、图表内嵌
5. 换一只标的（或换一期）重跑，报告不覆盖历史

## 目录结构

```
ai-quant-cli/
├── README.md
├── CLAUDE.md                       # 项目记忆：DAG 架构、数据契约、解析 / 出图实测要点
├── BUILD_PLAN.md                   # 从零构建计划（6 阶段 goal-only，给 CC 自驱）
├── lesson18-lab.md                 # 第 18 节实验手册（学生跟做）
├── requirements.txt                # pdfplumber / matplotlib / Jinja2（不引入任何 LLM SDK）
├── data/
│   ├── README.md                   # 年报下载说明（巨潮资讯网）
│   ├── 宁德时代2025年年度报告.pdf      # 样例年报（300750）
│   ├── 比亚迪2025年年度报告.pdf        # 样例年报（002594）
│   └── parsed/                     # L1 产物 financials.json（生成物，不入库）
├── analysis/
│   ├── findings_300750.json        # 宁德时代研判结果（CC 亲自产出，参考）
│   └── findings_002594.json        # 比亚迪研判结果（参考）
├── scripts/
│   ├── parse_report.py             # L1 解析入口 → financials.json + 恒等式自检
│   ├── make_figures.py             # L2 出图入口 → build/figures/*.png + manifest.json
│   ├── build_report.py             # L3 报告入口 → reports/*.html
│   └── run_pipeline.py             # L5 一键端到端（含 L4 研判闸门）
└── src/ai_quant/
    ├── common.py                   # 科目别名表 + JSON / 路径通用函数
    ├── parsing/                    # extract.py 解析三表 + checks.py 恒等式自检
    ├── viz/charts.py               # 出图 + 中文字体处理
    ├── report/build.py             # HTML 汇编
    └── pipeline/run.py             # 一键编排 + L4 闸门
```

> 运行产物 `data/parsed/`、`build/`、`reports/` 不入库（跑一次就有）；样例年报 PDF 已入库，其余 PDF 默认不入库。

## 数据

仓库已附宁德时代、比亚迪两份样例年报（`data/`），开箱即用。换标的从巨潮资讯网（cninfo.com.cn，A 股官方信披平台）按股票代码搜「年度报告」下载放进 `data/`（详见 [data/README.md](data/README.md)）。

## 相关课程章节

| 前置 | 内容 |
|---|---|
| 第 13 / 14 / 15 节 | 五步拆解心法、完成态公式、信号分诊与四段式架构（同一套业务流方法论） |
| 第 16 节 | Claude Code 基础（装好、接模型、终端对话） |
| 第 17 节 | 多文件协同与终端代码级重构（改已有代码）——本节进阶到「从空目录从零造系统」 |

| 后续 | 复用 |
|---|---|
| 第 19 节 | 本节交付的可复用系统 → 夜间自动化（OpenClaw Heartbeat 凌晨唤醒、经 MCP 驱动 Claude Code 自动跑、推送报告） |
