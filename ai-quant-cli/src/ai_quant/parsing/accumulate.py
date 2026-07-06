"""跨年报累积：把同公司多份 financials.json 按 period 缝合成全表时间序列。

每份年报含 current(期末)+prior(期初) 两期；多份去重合并 → 多年序列。
例：2024 报告(2024+2023) + 2025 报告(2025+2024) → 2023/2024/2025 三期全表。

趋势源 B（路 A 是年报内嵌的 summary_history，只覆盖头部指标；本模块覆盖全科目）。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def accumulate_timeseries(financials_list: list[dict[str, Any]]) -> dict[str, Any]:
    """把多份 financials 合并成 {periods, statements:{table:{item:{period:v}}}}。

    同一 (表, 科目, period) 以最新输入为准（后写覆盖）。
    """
    by_period: dict[str, dict[str, dict[str, dict[str, float]]]] = {}
    meta_refs: list[dict[str, Any]] = []

    for fin in financials_list:
        meta = fin.get("meta", {})
        company = meta.get("company", "")
        code = meta.get("stock_code", "")
        period = str(meta.get("period", ""))
        meta_refs.append({"company": company, "stock_code": code, "period": period})

        statements = fin.get("statements", {})
        for table_name, table in statements.items():
            for item, cp in table.items():
                for cp_key, label in (("current", period), ("prior", str(int(period) - 1) if period.isdigit() else "")):
                    value = cp.get(cp_key)
                    if value is None or not label:
                        continue
                    by_period.setdefault(label, {}).setdefault(table_name, {}).setdefault(item, {})[label] = value

    periods = sorted(p for p in by_period if p.isdigit())
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
