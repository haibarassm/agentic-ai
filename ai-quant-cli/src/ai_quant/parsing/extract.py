"""L1 解析：用 pdfplumber 的 extract_tables 把合并三表 + 多年汇总抽成结构化数据。

策略要点（实测宁德 2025 年报定型）：
- 锚点用「合并资产负债表 / 合并利润表 / 合并现金流量表」+ 列头（期末余额 / 本期金额）。
- 合并三表范围 = 从合并锚点到母公司锚点之前（母公司紧跟其后）。
- 行解析：每行非空单元格分类为「名」与「数值」；有数值的行 = 一条科目。
- 夹心折行（NAME-ONLY 行）双模式：
  - 汇总表：一律当后缀（汇总只 7 项，后缀都是真后缀）。
  - 三表：仅当以「的」开头才当后缀（捕获「归属于母公司所有者 + 的净利润」）；
    否则忽略（独立空项如「利息收入」本期无数值，丢之无碍，不污染前一条）。
- 科目名经 common.canonical_item 归一（别名表统一异名）。
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pdfplumber

from ..common import canonical_item, looks_numeric, parse_number

# 合并 / 母公司锚点 + 列头
_BS_CONSOL = "合并资产负债表"
_INC_CONSOL = "合并利润表"
_CF_CONSOL = "合并现金流量表"

# 报表在年报里的标准顺序：合并/母公司交替。某张合并表的边界 = 其后任意一张表（最早出现者）。
# 这样无论公司是否单列母公司表都能正确切分（比亚迪无母公司表 → 边界落在下一张合并表）。
_ALL_STATEMENT_ANCHORS = [
    _BS_CONSOL, "母公司资产负债表",
    _INC_CONSOL, "母公司利润表",
    _CF_CONSOL, "母公司现金流量表",
]


def _find_page(pdf, anchor: str, start_from: int = 0) -> int | None:
    """找第一个包含 anchor 的页（0 基）。列头差异大（期末余额/年度/日期），靠锚点本身定位。"""
    for idx in range(start_from, len(pdf.pages)):
        if anchor in _page_text(pdf, idx):
            return idx
    return None


def _find_boundary(pdf, start: int, after_anchors: list[str]) -> tuple[int, str]:
    """在 start 之后找最早出现的 after_anchors 之一 → (end_page_0基, 命中的 anchor)。"""
    best_idx = -1
    best_anchor = ""
    for anc in after_anchors:
        for idx in range(start + 1, len(pdf.pages)):
            if anc in _page_text(pdf, idx):
                if best_idx == -1 or idx < best_idx:
                    best_idx = idx
                    best_anchor = anc
                break
    if best_idx == -1:
        best_idx = min(start + 4, len(pdf.pages) - 1)
    return best_idx, best_anchor


def _statement_range(pdf, consol_anchor: str) -> tuple[int, int, str]:
    """返回 (start, end, stop_anchor)，end 含边界页，遇到 stop_anchor 行即停。"""
    start = _find_page(pdf, consol_anchor)
    if start is None:
        return (-1, -1, "")
    # 边界候选 = 本锚点之后的所有报表锚点（按文档顺序）
    pos = _ALL_STATEMENT_ANCHORS.index(consol_anchor)
    after = _ALL_STATEMENT_ANCHORS[pos + 1:]
    end, stop_anchor = _find_boundary(pdf, start, after)
    return (start, end, stop_anchor)


def _page_text(pdf, idx: int) -> str:
    try:
        return pdf.pages[idx].extract_text() or ""
    except Exception:
        return ""


def _anchor_y(page, anchor: str) -> float:
    """anchor 在该页的 top 坐标（用于过滤 anchor 上方的表）。找不到返回 0（不过滤）。"""
    if not anchor:
        return 0.0
    try:
        hits = page.search(anchor)
    except Exception:
        return 0.0
    if not hits:
        return 0.0
    return float(hits[0].get("top", 0.0))


def _row_name_matches(row: list[Any], anchor: str) -> bool:
    if not anchor:
        return False
    name, _ = _split_row(row)
    return anchor in name


def _flatten_rows(pdf, start: int, end: int, start_anchor: str = "", stop_anchor: str = "") -> list[list[Any]]:
    """把 [start, end] 闭区间各页的 table 行展平。

    - start 页：用 start_anchor 的 y 坐标，过滤掉 anchor 上方的表
      （避免 start 页顶部的上一张表尾巴混入，如 P116 顶部的母公司资产负债表）。
    - stop_anchor：遇到含 stop_anchor 的行立即停止（切掉下一张表，共页时用）。
    """
    rows: list[list[Any]] = []
    if start >= 0:
        anchor_top = _anchor_y(pdf.pages[start], start_anchor)
        for table_obj in pdf.pages[start].find_tables():
            if anchor_top and table_obj.bbox[1] < anchor_top:
                continue  # 该表在 anchor 上方，属于上一张表，跳过
            for row in table_obj.extract():
                if _row_name_matches(row, stop_anchor):
                    return rows
                rows.append(row)
    for idx in range(start + 1, end + 1):
        if idx < 0 or idx >= len(pdf.pages):
            continue
        for table in (pdf.pages[idx].extract_tables() or []):
            for row in table:
                if _row_name_matches(row, stop_anchor):
                    return rows
                rows.append(row)
    return rows


def _split_row(row: list[Any]) -> tuple[str, list[float]]:
    """一行 → (名, 数值列表)。去掉空单元格，文本归名、数字归值。"""
    cells = [c.strip() if isinstance(c, str) and c.strip() else "" for c in row]
    name_parts: list[str] = []
    values: list[float] = []
    for c in cells:
        if c == "":
            continue
        if looks_numeric(c):
            values.append(parse_number(c))
        else:
            name_parts.append(c)
    return "".join(name_parts), values


def _extract_items(rows: list[list[Any]], *, suffix_mode: str) -> list[tuple[str, list[float]]]:
    """从展平的行抽 [(canonical_name, values)]。

    suffix_mode:
      - "always": NAME-ONLY 行一律当后缀（汇总表用）
      - "de_only": NAME-ONLY 行仅当以「的」开头才当后缀（三表用）
      - "never": NAME-ONLY 行忽略
    """
    items: list[tuple[str, list[float]]] = []
    cur_name: str | None = None
    cur_values: list[float] | None = None

    def flush() -> None:
        nonlocal cur_name, cur_values
        if cur_name and cur_values is not None:
            items.append((canonical_item(cur_name), cur_values))
        cur_name, cur_values = None, None

    for row in rows:
        name, values = _split_row(row)
        if not name and not values:
            continue
        if values:  # 数据行 → 开新条目（先冲掉上一条）
            flush()
            cur_name = name
            cur_values = values
        else:  # NAME-ONLY 行
            if cur_values is not None and _is_suffix(name, suffix_mode):
                cur_name = (cur_name or "") + name
            # else: 忽略（独立空项 / 不符合后缀规则）
    flush()
    return items


def _is_suffix(name: str, mode: str) -> bool:
    if mode == "always":
        return True
    if mode == "de_only":
        return name.startswith("的")
    return False


def _to_current_prior(values: list[float]) -> dict[str, float]:
    """三表：取末两个数为期末/本期(current) 与 期初/上期(prior)。

    比亚迪等报表在「名」与「值」之间多一列「附注号」（如 `营业收入 45 803,964,958 777,102,455`），
    取末两个值可自动丢弃附注号；对无附注号的报表（宁德）等价。
    """
    out: dict[str, float] = {}
    if len(values) >= 2:
        out["current"] = values[-2]
        out["prior"] = values[-1]
    elif len(values) == 1:
        out["current"] = values[0]
    return out


def _text_line_to_nv(line: str) -> tuple[str, list[float]]:
    """文本行 → (名, 数值)。token 按是否数字分类；名片段拼接。

    适合『货币资金 333,512,927 303,511,993』（宁德）和
    『货币资金 1 75,424,747 102,738,734』（比亚迪，中间的 1 是附注号）。
    """
    tokens = line.split()
    name_parts: list[str] = []
    values: list[float] = []
    for tok in tokens:
        if looks_numeric(tok):
            values.append(parse_number(tok))
        else:
            name_parts.append(tok)
    return "".join(name_parts), values


def extract_statement(pdf, start: int, end: int, consol_anchor: str = "", parent_anchor: str = "") -> dict[str, dict[str, float]]:
    """抽一张合并报表（文本行驱动）→ {canonical科目: {current, prior}}。

    用 extract_text 而非 extract_tables：比亚迪等 PDF 的表格网格会让
    find_tables 按列切碎、丢掉科目名列；extract_text 给的是干净行。
    从 consol_anchor 行开始收集，遇到 parent_anchor 行即停。
    """
    out: dict[str, dict[str, float]] = {}
    if start < 0:
        return out
    started = (consol_anchor == "")
    for idx in range(start, end + 1):
        if idx < 0 or idx >= len(pdf.pages):
            continue
        for line in _page_text(pdf, idx).splitlines():
            s = line.strip()
            if not s:
                continue
            if not started:
                if consol_anchor and consol_anchor in s:
                    started = True
                continue
            if parent_anchor and parent_anchor in s:
                return out
            if "年年度报告" in s or "年度报告全文" in s:  # 跳过页眉
                continue
            name, values = _text_line_to_nv(s)
            if not name or not values:
                continue
            canon = canonical_item(name)
            if canon in out:
                continue
            cp = _to_current_prior(values)
            if cp:
                out[canon] = cp
    return out


# ---------- 多年汇总（趋势源 A）----------

_SUMMARY_ANCHOR = "主要会计数据"

# 汇总表里我们要抓的头部指标及其别名/正则
_SUMMARY_ITEM_PATTERNS = {
    "营业收入": re.compile(r"营业收入"),
    "归属于母公司所有者的净利润": re.compile(r"归属于.*?股东.*?净利润|归属于.*?所有者.*?净利润|归母净利润"),
    "归属于母公司所有者的扣除非经常性损益的净利润": re.compile(r"扣除非经常性损益.*?净利润"),
    "经营活动产生的现金流量净额": re.compile(r"经营活动.*?现金.*?净额"),
    "基本每股收益": re.compile(r"基本每股收益"),
    "稀释每股收益": re.compile(r"稀释每股收益"),
    "加权平均净资产收益率": re.compile(r"加权平均净资产收益率"),
    "资产总计": re.compile(r"^资产总[额计]|^总资产"),
    "归属于母公司所有者权益合计": re.compile(r"归属于.*?股东.*?净资产|归属于.*?所有者.*?净资产|归属于.*?净资产"),
}


def _detect_summary_unit(pdf, anchor_page: int) -> str:
    """汇总表自己的单位（可能与报表单位不同，如比亚迪汇总用元、报表用千元）。"""
    for idx in range(anchor_page, min(anchor_page + 3, len(pdf.pages))):
        m = re.search(r"单位(?:为)?[:：]\s*(元|千元|万元|百万元|亿元)", _page_text(pdf, idx))
        if m:
            return m.group(1)
    return ""


def _extract_summary_history(pdf) -> dict[str, Any]:
    """抽『主要会计数据』多年汇总（一般 3 年）。

    返回 {"periods": [...], "series": {...}, "unit": 汇总表原单位}。
    缺这张表则返回空结构。
    """
    anchor_page = None
    for idx in range(0, min(30, len(pdf.pages))):  # 汇总表都在前 30 页
        if _SUMMARY_ANCHOR in _page_text(pdf, idx):
            anchor_page = idx
            break
    if anchor_page is None:
        return {"periods": [], "series": {}, "unit": ""}

    tables: list = []
    for idx in range(anchor_page, min(anchor_page + 3, len(pdf.pages))):
        tables.extend(pdf.pages[idx].extract_tables() or [])
    rows = [row for table in tables for row in table]

    items = _extract_items(rows, suffix_mode="always")

    # 找列头表（含 "项目" + 若干年份）
    periods: list[str] = []
    for table in tables:
        for row in table:
            cells = [c.strip() if isinstance(c, str) and c.strip() else "" for c in row]
            joined = "".join(cells)
            years = re.findall(r"(20\d{2})\s*年", joined)
            if "项目" in joined and len(years) >= 2:
                periods = [y for y in years]  # 去重保序
                break
        if periods:
            break

    # 抽头部指标序列
    series: dict[str, list[float]] = {}
    for name, values in items:
        if not values:
            continue
        for canonical, pattern in _SUMMARY_ITEM_PATTERNS.items():
            if pattern.search(name) and canonical not in series:
                cleaned = _drop_pct_column(values)
                series[canonical] = cleaned
                break

    return {"periods": periods, "series": series, "unit": _detect_summary_unit(pdf, anchor_page)}


def _drop_pct_column(values: list[float]) -> list[float]:
    """汇总表数据行常为 [current, prior, 增减%(<1), prior2]；去掉中间的百分位列。

    判定：绝对值 < 1 的视为百分比（ROE/EPS 不是千元额而是比例/元，但也都 ≥1 或为比例）。
    宁德汇总里：营收/利润/现金流/资产是千元大数；EPS≈10-16；ROE≈0.24；增减%≈0.17。
    → 仅『增减%』和『ROE』<1。增减% 在中间位置（index 2），ROE 是单独行（不会误删）。
    """
    if len(values) >= 4 and abs(values[2]) < 1.5:
        return [values[0], values[1], values[3]]
    return values


# ---------- meta + 入口 ----------

def _detect_company(pdf) -> str:
    """封面/编制单位里取公司名。"""
    for idx in range(0, min(5, len(pdf.pages))):
        txt = _page_text(pdf, idx)
        for line in txt.splitlines():
            if "股份有限公司" in line or "有限公司" in line:
                name = re.sub(r"\s+", "", line.strip())
                if 4 <= len(name) <= 30:
                    return name
    return ""


def _detect_period(pdf) -> str:
    """报告期。年报→'2025'；季报/半年报→'2026Q1'/'2026H1'/'2026Q3'（带粒度后缀）。

    季报/半年报用**标题**判定（优先），因为季报 comparative 列含上年末 12-31 日期，
    会干扰纯日期判定。年报不含「第一季度/半年度/第三季度报告」标题，不会误命中。
    """
    # 1. 季报/半年报标题（前 5 页）——年报不会匹配，年报路径不受影响
    for idx in range(0, min(5, len(pdf.pages))):
        txt = _page_text(pdf, idx)
        m = re.search(r"(20\d{2})\s*年\s*第[一一]?\s*季度报告", txt)
        if m:
            return f"{m.group(1)}Q1"
        m = re.search(r"(20\d{2})\s*年\s*第[三三]\s*季度报告", txt)
        if m:
            return f"{m.group(1)}Q3"
        m = re.search(r"(20\d{2})\s*年\s*(?:半年度|中期)报告", txt)
        if m:
            return f"{m.group(1)}H1"
    # 2. 年报：资产负债表日期的年份（原有逻辑，不动）
    for idx in range(0, len(pdf.pages)):
        txt = _page_text(pdf, idx)
        m = re.search(r"(20\d{2})\s*年\s*12\s*月\s*31\s*日", txt)
        if m:
            return m.group(1)
    # 3. fallback：汇总表「YYYY 年度」
    for idx in range(0, min(30, len(pdf.pages))):
        txt = _page_text(pdf, idx)
        m = re.search(r"(20\d{2})\s*年度", txt)
        if m:
            return m.group(1)
    return ""


def _detect_unit(pdf, hint_page: int = -1) -> str:
    """单位（元/千元/万元）。优先取报表页附近的『单位：X』，避免被早段其它章节的『单位：元』误导。"""
    order: list[int] = []
    if hint_page >= 0:
        order.extend(range(max(0, hint_page), min(hint_page + 3, len(pdf.pages))))
    order.extend(range(len(pdf.pages)))
    seen = set()
    for idx in order:
        if idx in seen:
            continue
        seen.add(idx)
        txt = _page_text(pdf, idx)
        m = re.search(r"单位(?:为)?[:：]\s*(元|千元|万元|百万元|亿元)", txt)
        if m:
            return m.group(1)
    return "元"


def _detect_stock_code(pdf, hint: str | None) -> str:
    """股票代码：封面『股票代码 300750』或 hint。"""
    if hint:
        return hint
    for idx in range(0, min(15, len(pdf.pages))):
        txt = _page_text(pdf, idx)
        m = re.search(r"股票代码\s*[:：]?\s*(\d{6})", txt)
        if m:
            return m.group(1)
        m = re.search(r"\b(60\d{4}|30\d{4}|00\d{4}|688\d{3})\b", txt)
        if m:
            return m.group(1)
    return ""


def extract_financials(pdf_path: str | Path, *, stock_code: str | None = None) -> dict[str, Any]:
    """解析一份年报 PDF → financials dict（落盘为 financials.json）。"""
    path = Path(pdf_path)
    pdf = pdfplumber.open(str(path))

    bs_start, bs_end, bs_stop = _statement_range(pdf, _BS_CONSOL)
    inc_start, inc_end, inc_stop = _statement_range(pdf, _INC_CONSOL)
    cf_start, cf_end, cf_stop = _statement_range(pdf, _CF_CONSOL)

    balance_sheet = extract_statement(pdf, bs_start, bs_end, consol_anchor=_BS_CONSOL, parent_anchor=bs_stop)
    income = extract_statement(pdf, inc_start, inc_end, consol_anchor=_INC_CONSOL, parent_anchor=inc_stop)
    cash_flow = extract_statement(pdf, cf_start, cf_end, consol_anchor=_CF_CONSOL, parent_anchor=cf_stop)
    summary_history = _extract_summary_history(pdf)

    from .checks import balance_identity_check
    from ..common import unit_scale
    checks = balance_identity_check(balance_sheet)

    # 汇总表单位归一到报表单位（比亚迪汇总用元、报表用千元，差 1000 倍）。
    # 注意：EPS（元/股）、ROE（比率/百分数）不是金额，绝不能跟着金额一起缩放，
    # 否则会被错误地除以 1000（比亚迪曾因此把 EPS 3.58→0.00358、ROE 15.31%→0.015%）。
    _NON_MONETARY_SERIES = {"基本每股收益", "稀释每股收益", "加权平均净资产收益率"}
    summary_unit = summary_history.get("unit") or ""
    target_unit = _detect_unit(pdf, hint_page=bs_start)
    if summary_unit and target_unit and summary_unit != target_unit:
        scale = unit_scale(summary_unit, target_unit)
        for key, vals in summary_history.get("series", {}).items():
            if key in _NON_MONETARY_SERIES:
                continue
            summary_history["series"][key] = [v * scale if v is not None else v for v in vals]
    summary_history["unit"] = target_unit or summary_unit

    meta = {
        "company": _detect_company(pdf),
        "stock_code": _detect_stock_code(pdf, stock_code),
        "period": _detect_period(pdf),
        "currency": "CNY",
        "unit": _detect_unit(pdf, hint_page=bs_start),
        "source_pdf": path.name,
        "parsed_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "statement_pages": {
            "balance_sheet": [bs_start + 1, bs_end + 1] if bs_start >= 0 else None,
            "income": [inc_start + 1, inc_end + 1] if inc_start >= 0 else None,
            "cash_flow": [cf_start + 1, cf_end + 1] if cf_start >= 0 else None,
        },
    }
    pdf.close()

    return {
        "meta": meta,
        "statements": {
            "balance_sheet": balance_sheet,
            "income": income,
            "cash_flow": cash_flow,
        },
        "summary_history": summary_history,
        "checks": checks,
    }


def find_statement_ranges(pdf_path: str | Path) -> dict[str, tuple[int, int] | None]:
    """诊断用：返回三张合并报表的页范围（1 基闭区间）。"""
    pdf = pdfplumber.open(str(pdf_path))
    bs = _statement_range(pdf, _BS_CONSOL)
    inc = _statement_range(pdf, _INC_CONSOL)
    cf = _statement_range(pdf, _CF_CONSOL)
    pdf.close()
    return {
        "balance_sheet": (bs[0] + 1, bs[1] + 1) if bs[0] >= 0 else None,
        "income": (inc[0] + 1, inc[1] + 1) if inc[0] >= 0 else None,
        "cash_flow": (cf[0] + 1, cf[1] + 1) if cf[0] >= 0 else None,
    }


# 便于直接 `python -m ai_quant.parsing.extract data/x.pdf`
if __name__ == "__main__":
    import sys

    data = extract_financials(sys.argv[1] if len(sys.argv) > 1 else "data/宁德时代2025年年度报告.pdf")
    print(json.dumps(data, ensure_ascii=False, indent=2))
