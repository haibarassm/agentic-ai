#!/usr/bin/env python3
"""港版财报解析入口：PDF → data/parsed/financials_<code>_<period>.json + 恒等式自检。

用法：
    python scripts/parse_hk_report.py data/26Q1_CN_AC.pdf --code 01810
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

from ai_quant.parsing.hk_extract import extract_hk_financials  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="港版（HK-IFRS）财报解析")
    ap.add_argument("pdf", help="PDF 路径")
    ap.add_argument("--code", default=None, help="股票代码（如 01810）")
    ap.add_argument("--out-dir", default="data/parsed")
    args = ap.parse_args()

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        print(f"❌ PDF 不存在: {pdf_path}", file=sys.stderr)
        return 1

    print(f"==> 解析（港版 HK-IFRS）{pdf_path.name} ...")
    fin = extract_hk_financials(pdf_path, stock_code=args.code)

    code = fin["meta"]["stock_code"] or "unknown"
    period = fin["meta"]["period"] or "unknown"
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    # 港版多份报告（年报+季报）共存：文件名带 period
    out_path = out_dir / f"financials_{code}_{period}.json"
    out_path.write_text(json.dumps(fin, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"    公司: {fin['meta']['company']}  代码: {code}  期: {period}  格式: {fin['meta']['format']}")
    print(f"    报表页: {fin['meta']['statement_pages']}")
    print(f"    科目数: 资产负债表 {len(fin['statements']['balance_sheet'])} / "
          f"利润表 {len(fin['statements']['income'])} / 现金流量表 {len(fin['statements']['cash_flow'])}")

    chk = fin["checks"]["balance_identity"]
    cur_ok = chk.get("current", {}).get("ok", False)
    pri_ok = chk.get("prior", {}).get("ok", False)
    for key in ("current", "prior"):
        c = chk.get(key, {})
        mark = "✅" if c.get("ok") else "❌"
        lhs = c.get("lhs")
        rhs = c.get("rhs")
        lhs_s = f"{lhs:,.0f}" if lhs else "缺失"
        rhs_s = f"{rhs:,.0f}" if rhs else "缺失"
        print(f"    {mark} {key:7}: 资产 {lhs_s}  ==  负债+权益 {rhs_s}  (diff={c.get('diff')})")

    print(f"\n✅ 已落盘 {out_path}")
    if not (cur_ok and pri_ok):
        print("⚠️  恒等式未通过，检查科目抓取/分段", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
