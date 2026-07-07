"""L3 报告汇编层：financials + findings + figures → 自包含 HTML。"""

from .build import build_report, load_json

__all__ = ["build_report", "load_json"]
