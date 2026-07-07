#!/usr/bin/env python3
"""OCR 解析入口：字体损坏的 PDF → data/parsed/financials_<code>_<period>.json。

用法：
    python scripts/parse_ocr_report.py data/Xiaomi\ 2025\ AR_c.pdf --code 01810 --summary-page 8
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

from ai_quant.parsing.ocr_extract import extract_ocr_financials  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="OCR 解析（字体损坏的 PDF）")
    ap.add_argument("pdf", help="PDF 路径")
    ap.add_argument("--code", default=None)
    ap.add_argument("--summary-page", type=int, default=None, help="五年摘要页码（不传则前12页扫描，慢）")
    ap.add_argument("--out-dir", default="data/parsed")
    args = ap.parse_args()

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        print(f"❌ PDF 不存在: {pdf_path}", file=sys.stderr)
        return 1

    print(f"==> OCR 解析 {pdf_path.name} ...")
    fin = extract_ocr_financials(pdf_path, stock_code=args.code, summary_page=args.summary_page)

    code = fin["meta"]["stock_code"]
    period = fin["meta"]["period"]
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"financials_{code}_{period}.json"
    out_path.write_text(json.dumps(fin, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"    公司: {fin['meta']['company']}  代码: {code}  期: {period}  摘要页: P{fin['meta']['summary_page']}")
    sh = fin["summary_history"]
    print(f"    五年序列: {sh['periods']}，{len(sh['series'])} 个指标")
    print(f"    科目数: 资产负债表 {len(fin['statements']['balance_sheet'])} / 利润表 {len(fin['statements']['income'])} / 现金流 {len(fin['statements']['cash_flow'])}")

    chk = fin["checks"]["balance_identity"]
    for key in ("current", "prior"):
        c = chk.get(key, {})
        mark = "✅" if c.get("ok") else "❌"
        lhs = c.get("lhs"); rhs = c.get("rhs")
        print(f"    {mark} {key:7}: 资产 {f'{lhs:,.0f}' if lhs else '缺失'}  ==  负债+权益 {f'{rhs:,.0f}' if rhs else '缺失'}  (diff={c.get('diff')})")

    print(f"\n✅ 已落盘 {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
