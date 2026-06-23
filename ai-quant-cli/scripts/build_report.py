#!/usr/bin/env python3
"""CLI：数据 + 图 + 研判 → reports/report_<period>.html（L3 报告层入口）。

需先有 data/parsed/financials.json、analysis/findings.json，以及（可选但推荐）
build/figures/ 下的图与 manifest.json。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_quant.report.build import build_report  # noqa: E402


def main() -> int:
    out = build_report()
    size_kb = out.stat().st_size / 1024
    print(f"[报告] 生成 → {out}  ({size_kb:.0f} KB，图表已 base64 内嵌)")
    print(f"[打开] open '{out}'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
