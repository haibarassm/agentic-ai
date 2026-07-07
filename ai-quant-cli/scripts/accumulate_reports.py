#!/usr/bin/env python3
"""路 B：跨报告拼接同公司多份 financials → 全科目时间序列。

用法：
    python scripts/accumulate_reports.py --code 300750
    python scripts/accumulate_reports.py data/parsed/financials_300750_2025.json data/parsed/financials_300750_2026Q1.json

输出：analysis/stitched_<code>.json + 终端打印「关键科目 × 期」表（亿元）。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

from ai_quant.common import to_yi  # noqa: E402
from ai_quant.parsing.accumulate import accumulate_from_dir, accumulate_timeseries  # noqa: E402

# 拼接表里展示的关键科目（覆盖三表的核心勾稽项）。
_KEY_ITEMS: list[tuple[str, str]] = [
    ("balance_sheet", "资产总计"),
    ("balance_sheet", "负债合计"),
    ("balance_sheet", "所有者权益合计"),
    ("balance_sheet", "存货"),
    ("income", "营业收入"),
    ("income", "归属于母公司所有者的净利润"),
    ("cash_flow", "经营活动产生的现金流量净额"),
]


def _cell(value: float | None) -> str:
    if value is None:
        return f"{'—':>14}"
    return f"{to_yi(value):>14.2f}"


def main() -> int:
    ap = argparse.ArgumentParser(description="路 B：跨报告拼接")
    ap.add_argument("paths", nargs="*", help="多份 financials JSON 路径（不传则按 --code 在 parsed-dir 查）")
    ap.add_argument("--code", default=None, help="股票代码（paths 未传时用）")
    ap.add_argument("--parsed-dir", default="data/parsed")
    ap.add_argument("--out", default=None, help="输出 JSON 路径（默认 analysis/stitched_<code>.json）")
    args = ap.parse_args()

    if args.paths:
        fins = []
        for p in args.paths:
            pp = Path(p)
            if not pp.exists():
                print(f"❌ 找不到 {p}", file=sys.stderr)
                return 1
            fins.append(json.loads(pp.read_text(encoding="utf-8")))
        result = accumulate_timeseries(fins)
    else:
        if not args.code:
            print("❌ 请传 paths，或 --code", file=sys.stderr)
            return 1
        result = accumulate_from_dir(_ROOT / args.parsed_dir, stock_code=args.code)

    if not result or not result.get("periods"):
        print("❌ 没有可拼接的数据（检查 parsed-dir 下是否有对应 financials*.json）", file=sys.stderr)
        return 1

    code = result.get("stock_code") or "unknown"
    periods = result["periods"]
    out = Path(args.out) if args.out else (_ROOT / "analysis" / f"stitched_{code}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"==> 拼接 {len(result['sources'])} 份报告 → {len(periods)} 期")
    print(f"    公司: {result.get('company')}  代码: {code}")
    print(f"    期: {periods}")
    for s in result["sources"]:
        print(f"      - {s.get('period','?'):<10} {s.get('source_pdf','')}")

    print(f"\n    关键科目（亿元）：")
    print(f"    {'科目':<28}" + "".join(f"{p:>14}" for p in periods))
    for tbl, item in _KEY_ITEMS:
        row = result["statements"].get(tbl, {}).get(item, {})
        print(f"    {item:<26}" + "".join(_cell(row.get(p)) for p in periods))

    print(f"\n✅ 落盘 {out.relative_to(_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
