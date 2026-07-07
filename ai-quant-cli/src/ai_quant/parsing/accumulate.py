"""跨报告累积：把同公司多份 financials.json 按 period 缝合成全表时间序列（路 B）。

每份年报含 current(期末)+prior(期初) 两期；多份去重合并 → 多年序列。
例：2024 年报(2024+2023) + 2025 年报(2025+2024) → 2023/2024/2025 三期全表。

支持季度/半年度报告（period 形如 '2026Q1'/'2026H1'/'2026Q3'）。
prior 标签按报表类型区分（A 股/港版季报的勾稽规则）：
- 资产负债表：current=期末，prior=**上年度末** → 标上一年年度 period（'2025'）。
- 利润表/现金流量表：current=本期，prior=**上年同期** → 标同粒度上一年（'2025Q1'）。
年报路径（period 无粒度）不受影响。
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

# 粒度 → 期末月份（排序用）。年度=12。
_GRANULARITY_MONTH: dict[str, int] = {"": 12, "Q1": 3, "H1": 6, "Q2": 6, "Q3": 9}


def _split_period(label: str) -> tuple[int, str]:
    """'2025' → (2025, '')；'2026Q1' → (2026, 'Q1')；'2026H1' → (2026, 'H1')。"""
    m = re.fullmatch(r"(20\d{2})(Q[123]|H1)?", str(label).strip())
    if not m:
        return (0, "")
    return (int(m.group(1)), m.group(2) or "")


def _prior_period(label: str) -> str:
    """上一年同粒度（利润表/现金流用）：'2025'→'2024'，'2026Q1'→'2025Q1'。"""
    year, gran = _split_period(label)
    if year == 0:
        return ""
    return f"{year - 1}{gran}"


def _bs_prior_period(label: str) -> str:
    """资产负债表上期 = 上年度末 → 上一年年度 period：'2026Q1'→'2025'，'2025'→'2024'。"""
    year, _ = _split_period(label)
    if year == 0:
        return ""
    return str(year - 1)


def _period_sort_key(label: str) -> tuple[int, int]:
    """排序键：(年, 期末月)。'2025'→(2025,12)；'2025Q1'→(2025,3)。保证 2025Q1 < 2025 < 2026Q1。"""
    year, gran = _split_period(label)
    return (year, _GRANULARITY_MONTH.get(gran, 12))


def accumulate_timeseries(financials_list: list[dict[str, Any]]) -> dict[str, Any]:
    """把多份 financials 合并成 {periods, statements:{table:{item:{period:v}}}, sources}。

    同一 (表, 科目, period) 以最新输入为准（后写覆盖）。
    """
    by_period: dict[str, dict[str, dict[str, dict[str, float]]]] = {}
    meta_refs: list[dict[str, Any]] = []

    for fin in financials_list:
        meta = fin.get("meta", {})
        company = meta.get("company", "")
        code = meta.get("stock_code", "")
        period = str(meta.get("period", "")).strip()
        meta_refs.append({"company": company, "stock_code": code, "period": period,
                          "source_pdf": meta.get("source_pdf", "")})

        is_prior_period = _prior_period(period)      # IS/CF 上期 = 上年同期
        bs_prior = _bs_prior_period(period)          # BS  上期 = 上年度末
        statements = fin.get("statements", {})
        for table_name, table in statements.items():
            prior_label = bs_prior if table_name == "balance_sheet" else is_prior_period
            for item, cp in table.items():
                for cp_key, label in (("current", period), ("prior", prior_label)):
                    value = cp.get(cp_key)
                    if value is None or not label:
                        continue
                    by_period.setdefault(label, {}).setdefault(table_name, {}).setdefault(item, {})[label] = value

    # 丢弃解析失败的空 period（year==0），其余按时间排序
    periods = sorted((p for p in by_period if _split_period(p)[0] != 0), key=_period_sort_key)

    pivoted: dict[str, dict[str, dict[str, dict[str, float]]]] = {}
    for period in periods:
        for table_name, table in by_period[period].items():
            for item, pv in table.items():
                pivoted.setdefault(table_name, {}).setdefault(item, {}).update(pv)

    company = meta_refs[0]["company"] if meta_refs else ""
    code = meta_refs[0]["stock_code"] if meta_refs else ""
    return {
        "company": company,
        "stock_code": code,
        "periods": periods,
        "statements": pivoted,
        "sources": meta_refs,
    }


def accumulate_from_dir(parsed_dir: str | Path, *, stock_code: str | None = None) -> dict[str, Any] | None:
    """读 parsed_dir 下所有 financials*.json，按 stock_code 过滤后缝合。"""
    parsed_dir = Path(parsed_dir)
    files = sorted(parsed_dir.glob("financials*.json"))
    fins: list[dict[str, Any]] = []
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if stock_code and data.get("meta", {}).get("stock_code") != stock_code:
            continue
        fins.append(data)
    if not fins:
        return None
    return accumulate_timeseries(fins)
