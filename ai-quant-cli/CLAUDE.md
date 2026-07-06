# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> 本文件只管 `ai-quant-cli/` 子项目。仓库根 `agentic-ai/CLAUDE.md` 是课程总览，与本文件并存。

## 这个项目是什么

从 A 股年报 PDF 造一个本地投研系统：解析合并三张报表 → **由 Claude Code 亲自做财务风险研判** → 出图 → 汇编单页 HTML 投研报告。Python 脚本只做确定性工作（解析 PDF / 出图 / 汇编），研判由人（Claude Code）亲自完成。

## 铁律（不可违背）

1. **分析判断由 Claude Code 亲自做，代码不碰判断。** 财务风险研判、三表勾稽结论由我直接读 `financials.json` 后产出成 `analysis/findings_<code>.json`；Python 脚本只做解析、出图、汇编。
2. **任何脚本里都不调用大模型 API**，不引入 LLM SDK / 在线服务（`requirements.txt` 只有 pdfplumber / matplotlib / Jinja2）。
3. **L4 是人工闸门，pipeline 进 L3 前必须检查 `findings_<code>.json` 就位**：缺则报错停下（exit code 2），绝不静默出半成品报告。L1/L2 的确定性产物可以先生成，但报告这一步被闸门挡住。
4. 每条研判结论必须挂 `evidence`（指向 `报表 + 科目 + 期间 + 值`），保证可追溯。
5. 年报 PDF：仓库已附宁德(300750) / 比亚迪(002594) 两份 2025 年报样例；`data/parsed/`、`build/` 视为生成产物（不入库，从 PDF 重跑即得）；`analysis/findings_*.json` 是 L4 人工研判产物，**入库**（是核心交付物，非脚本生成）。

## 架构（DAG，不是直线流水线）

```
            ┌──→ L2 出图 (viz) ───── build/figures/*.png ──┐
L1 解析 ──→ ┤                                              ├──→【L4 闸门】──→ L3 报告
(parsing)   └──→ L4 研判 (我·人工) ─ analysis/findings.json ┘   findings 在?     (report)
            financials.json  扇出                              ↓ 否 → 停(exit 2)
                                                              是 → 汇编 → build/reports/*.html
```

- **唯一硬约束**：`L1 最先、L3 最后`，L3 前有 L4 闸门。中间 **L2 出图** 与 **L4 研判** 互不依赖、可并行。
- **L4 不是脚本**：是我读 `financials.json` 后亲自产出 `analysis/findings_<code>.json`。pipeline 不自动生成它，只检查它是否就位。
- 每层只依赖上游落盘的 JSON 文件，不互相 import 业务逻辑。

| 层 | 包 | 职责 | 产出 |
|---|---|---|---|
| L1 解析 | `src/ai_quant/parsing/` | PDF 定位**合并**三表 + 主要会计数据多年汇总，抽期末/期初，会计恒等式自检 | `data/parsed/financials_<code>.json` |
| L2 出图 | `src/ai_quant/viz/` | 读 financials 渲染图，处理中文字体与负号 | `build/figures/*.png` + `manifest.json` |
| L4 研判 | 我（非代码） | 隐性风险研判 + 交叉验证，每条挂 evidence | `analysis/findings_<code>.json` |
| L3 报告 | `src/ai_quant/report/` | Jinja2 汇编单页 HTML，图片 base64 内嵌（自包含可离线分发） | `build/reports/report_<code>_<period>_<ts>.html` |
| L5 编排 | `src/ai_quant/pipeline/` | 一键重跑，含 L4 闸门检查 | 终端日志 |

CLI 入口在 `scripts/`：`parse_report.py` / `make_figures.py` / `build_report.py` / `run_pipeline.py`，各自薄封装对应层。

## 数据契约

**`data/parsed/financials_<code>.json`**（L1 产出，L2/L3/L4 都读）：
```jsonc
{
  "meta": {"company","stock_code","period","currency","unit","source_pdf","parsed_at","statement_pages"},
  "statements": {
    "balance_sheet": {"<科目>": {"current": 数, "prior": 数}},
    "income":        {"<科目>": {"current": 数, "prior": 数}},
    "cash_flow":     {"<科目>": {"current": 数, "prior": 数}}
  },
  "summary_history": {                       // 年报内嵌「主要会计数据」多年汇总（路A，趋势图数据源）
    "periods": ["2025","2024","2023"],
    "series":  {"营业收入": [...], "归属于母公司所有者的净利润": [...], "加权平均净资产收益率": [...], ...},
    "unit": "千元"
  },
  "checks": {"balance_identity": {"current": {"ok","lhs","rhs","diff","tolerance"},
                                  "prior":   {"ok","lhs","rhs","diff","tolerance"}}}
}
```
约定：金额一律 `float`（千元、去千分位、括号负数转负值）；期末=`current`、期初=`prior`；科目用规范中文名（异名由 `common.py:_ITEM_ALIASES` 归一，如『股东权益合计』→『所有者权益合计』、『四、净利润』→『净利润』）。

**`analysis/findings_<code>.json`**（我产出，L3 读）：
```jsonc
{
  "meta": {"stock_code","company","period","unit","analyst","analyzed_at","source"},
  "risk_findings": [{
    "id":"R1", "title":"...", "severity":"high|medium|low",
    "category":"存货|盈利质量|资本开支|偿债|应收|...",
    "summary":"一句话", "narrative":"详细判断（我写的）",
    "evidence":[{"statement":"balance_sheet","item":"存货","period":"current","value":94526239}],
    "metrics":{...}
  }],
  "cross_checks": [{"id":"X1","name":"...","verdict":"pass|warn|fail","summary":"...","evidence":[...],"metrics":{...}}],
  "overall": "总体结论（我写的）"
}
```
**每条结论必须挂 `evidence`**（指向 `报表 + 科目 + 期间 + 值`），保证可追溯。

**`build/figures/manifest.json`**：`[{"id","path","title","caption"}]`，path 相对项目根，报告层读图后 base64 内嵌。

## 常用命令（Windows / Git Bash）

> **环境坑（实测，记 memory 了）**：本机无 `python3`/`rsync`，venv 在 `.venv/Scripts/`（不是 `bin/`）；清华镜像对部分 wheel 403，换阿里云 `https://mirrors.aliyun.com/pypi/simple/`；pip 前先 `unset ALL_PROXY all_proxy`（socks 代理会让构建子进程报 `metadata-generation-failed`）。

```bash
cd ai-quant-cli
python -m venv .venv && .venv/Scripts/activate
unset ALL_PROXY all_proxy
pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/

# 单层入口
python scripts/parse_report.py  data/<年报>.pdf [--code 300750]   # L1 → financials_<code>.json + 恒等式自检
python scripts/make_figures.py   [--code 300750]                  # L2 → build/figures/*.png + manifest.json
python scripts/build_report.py   [--code 300750]                  # L3 → build/reports/report_<code>_<period>_<ts>.html

# 一键全流程（L5）
python scripts/run_pipeline.py --code 300750 --pdf data/宁德时代2025年年度报告.pdf   # 全链路
python scripts/run_pipeline.py --code 300750 --skip-parse --skip-figures             # 只补 L3（findings 已就位）
```
> 一键编排在进 L3 前做 **L4 闸门**：按 code 定位 `analysis/findings_<code>.json`，缺失则 exit code 2 停下、不出报告。L4 研判由分析者人工产出，编排不自动生成。
>
> **多公司**：解析层动态识别公司名/单位/期；股票代码封面识别不到时 `--code` 显式指定（比亚迪 `--code 002594`）。已实测宁德(300750) 与比亚迪(002594) 两家可并存重跑，恒等式均 diff=0.0。

## 解析层实测要点（L1 落定）

- **定位用编号锚点**，不靠固定页码：财报正文 `1、合并资产负债表` / `3、合并利润表` / `5、合并现金流量表`（母公司是 2/4/6）。`_statement_range` 用「下一个合并锚点」做边界，兼容比亚迪没有母公司表的情况。
- **两种表格形态都要兼容**：宁德表格框线完整 → `extract_tables` 干净；比亚迪表格被列切碎 → 退到 `extract_text` 按行 token 分类（`_text_line_to_nv`）。
- **夹心折行**：长科目名被劈成「名上半 / 纯数字行 / 名下半」，状态机拼回。改解析后务必重看恒等式自检 + 几条跨表勾稽是否仍成立。
- **单位**：报表页附近找 `单位：千元/元/万元`，meta.unit 存原文单位，数值按原文存不擅自换算。
- **汇总表单位归一坑（重要，曾出 bug）**：比亚迪「主要会计数据」汇总表用「元」、报表用「千元」，差 1000 倍。`extract_financials` 末尾会按 `unit_scale` 归一汇总表金额到报表单位——**但 EPS（元/股）、ROE（比率）不是金额，必须跳过缩放**（`_NON_MONETARY_SERIES`），否则 EPS 3.58→0.00358、ROE 15.31%→0.015%，趋势图全错。
- **自检**：`资产总计 == 负债合计 + 所有者权益合计`，期末/期初各一组，容差 1e-4。两家样例 diff 均为 0.0。

## 出图层渲染约定（L2 落定）

- **后端**：`matplotlib.use("Agg")`（无界面，直接出 PNG）。
- **中文字体（必踩坑，已修）**：默认会乱码（缺字变方框 □□□）。`viz/charts.py:setup_chinese_font()` 用**跨平台回退链**挑本机第一个可用 CJK 字体，写进 `rcParams["font.sans-serif"]`：
  - Windows：`Microsoft YaHei` → `SimHei` → `SimSun`（实测本机命中 Microsoft YaHei）
  - macOS：`PingFang SC` → `Hiragino Sans GB` → `Arial Unicode MS` → `Heiti SC`
  - Linux：`Noto Sans CJK SC` → `Source Han Sans SC` → `WenQuanYi Zen Hei`
  - 兜底：任何名字含 `Hei/Song/Kai/Yuan/CJK/SC` 的字体。新图一律先调 `setup_chinese_font()`。
- **负号（必踩坑，已修）**：必须 `rcParams["axes.unicode_minus"] = False`，否则负号渲染成方框（本项目有大量负值：财务费用、投资活动现金流等）。
- **金额展示**：源数据是千元，出图统一 ÷1e5 换算成「亿元」（`common.py:to_yi`）。
- **None 安全**：报表里有缺 prior 的科目，柱状图用 `(_yi(v) or 0)` 兜底，避免 None 拼接崩溃。
- **子串匹配定位现金流科目**：不同公司命名带乱码尾巴（如比亚迪『投资活动使用的现金流量净额))』），用 `needle in k and "净额" in k` 子串匹配，不写死 key。
- **产出**：`build/figures/*.png` + `manifest.json`，report 层 base64 内嵌。
- 当前 5 张图：`revenue_profit`（营收与归母净利润多年趋势）/ `profitability`（净利率 + ROE 双轴）/ `ocf_vs_ni`（经营现金流 vs 归母净利润）/ `balance_structure`（资产=负债+权益堆叠柱）/ `cashflow_three`（三大活动现金流净额）。

## 报告层（L3）

- Jinja2 渲染单页 HTML，**图片 base64 内嵌**（`data:image/png;base64,...`），单文件可离线分发/放 CDN，无外部依赖。
- 视图模型在 `report/build.py` 里预算（金额转亿元、ROE×100、变动率），模板只做展示，不做复杂条件。
- `format_value` 同时注册为 Jinja filter 和 global，模板里 `{{ v|format_value }}` 与 `{{ format_value(v) }}` 都能用。
- 命名 `report_<code>_<period>_<yyyymmdd_HHMM>.html`，多次运行互不覆盖。

## 技术选型

- **PDF 解析**：`pdfplumber`（`extract_tables` + `extract_text` 双模式）；纯 Python 无系统依赖，避开 JVM 的 tabula/Camelot。
- **出图**：`matplotlib` 离线静态 PNG。
- **报告**：`Jinja2` 模板 + base64 内嵌，单页自包含 HTML。
- **数据交换**：全用 JSON 落盘，层间解耦、可单独重跑。

## 已知风险点（实现时注意）

1. **别抓错报表**：年报同时含「母公司」与「合并」三表，必须锁定**合并**报表标题；比亚迪甚至没有母公司表，边界要用「下一个合并锚点」。
2. **数字格式**：千分位逗号、负数括号 `(1,234)`、单位（元/千元/万元）、跨页续表、空单元格、附注号列（`values[-2:]` 取末两列）。
3. **汇总表单位归一**：见上文「解析层实测要点」——EPS/ROE 绝不能跟着金额一起缩放。
4. **matplotlib 中文乱码 + 负号方框**：L2 必踩，配好 `setup_chinese_font()` + `unicode_minus=False` 后**把修法写回本文件**（已回填）。
5. **趋势图期数**：单份年报内嵌的「主要会计数据」通常给 3 期（路A），是趋势图的数据源；若要更长周期需跨多份年报累积（路B，`parsing/accumulate.py`）。
6. **恒等式容差**：四舍五入/单位换算有残差，自检设 1e-4 容差而非严格相等。
