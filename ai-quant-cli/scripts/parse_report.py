#!/usr/bin/env python3
"""CLI：解析年报 PDF → data/parsed/financials.json（L1 解析层入口）。

用法：
    python scripts/parse_report.py data/<年报>.pdf [-o data/parsed/financials.json]

只做解析与会计恒等式自检，不做任何财务分析（铁律：代码不碰判断、不调 API）。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 让脚本能 import src/ai_quant
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_quant.parsing.extract import extract_financials  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="解析年报 PDF 的合并三表")
    ap.add_argument("pdf", help="年报 PDF 路径")
    ap.add_argument(
        "-o", "--output", default=str(ROOT / "data" / "parsed" / "financials.json")
    )
    args = ap.parse_args()

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        print(f"[错误] 找不到 PDF：{pdf_path}", file=sys.stderr)
        return 1

    print(f"[解析] {pdf_path}")
    data = extract_financials(str(pdf_path))

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    # 解析概况 + 恒等式自检结果打印到终端，方便逐阶段截图核对
    st = data["statements"]
    print(f"[完成] 落盘 → {out}")
    print(
        f"  科目数：资产负债表 {len(st['balance_sheet'])}"
        f" / 利润表 {len(st['income'])}"
        f" / 现金流量表 {len(st['cash_flow'])}"
    )
    bi = data["checks"]["balance_identity"]
    print(f"  会计恒等式自检：{'✓ 通过' if bi['ok'] else '✗ 不平'}")
    for period in ("current", "prior"):
        p = bi[period]
        tag = "期末" if period == "current" else "期初"
        for k, v in p.items():
            if k == "ok":
                continue
            mark = "✓" if v["ok"] else "✗"
            diff = v.get("diff")
            print(f"    [{tag}] {mark} {k}  diff={diff}")
    return 0 if bi["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
