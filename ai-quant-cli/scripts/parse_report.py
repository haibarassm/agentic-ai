#!/usr/bin/env python3
"""L1 解析入口：年报 PDF → data/parsed/financials_<code>.json + 会计恒等式自检。

用法：
    python scripts/parse_report.py data/<年报>.pdf [--code 300750]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 让脚本无论从哪运行都能 import ai_quant
_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

from ai_quant.parsing.extract import extract_financials  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="L1 解析年报 PDF → financials.json")
    parser.add_argument("pdf", help="年报 PDF 路径")
    parser.add_argument("--code", default=None, help="股票代码（封面识别不到时显式指定）")
    parser.add_argument("--out-dir", default="data/parsed", help="输出目录")
    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        print(f"❌ PDF 不存在: {pdf_path}", file=sys.stderr)
        return 1

    print(f"==> 解析 {pdf_path.name} ...")
    fin = extract_financials(pdf_path, stock_code=args.code)

    code = fin["meta"]["stock_code"] or "unknown"
    period = fin["meta"]["period"] or "unknown"
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"financials_{code}.json"
    out_path.write_text(json.dumps(fin, ensure_ascii=False, indent=2), encoding="utf-8")

    # 报告
    print(f"    公司: {fin['meta']['company']}  代码: {code}  期: {period}  单位: {fin['meta']['unit']}")
    print(f"    报表页: {fin['meta']['statement_pages']}")
    print(f"    科目数: 资产负债表 {len(fin['statements']['balance_sheet'])} / "
          f"利润表 {len(fin['statements']['income'])} / "
          f"现金流量表 {len(fin['statements']['cash_flow'])}")
    sh = fin["summary_history"]
    print(f"    多年汇总: {len(sh['periods'])} 期 {sh['periods']}，{len(sh['series'])} 个指标")

    print("\n==> 会计恒等式自检（资产 = 负债 + 所有者权益）")
    all_ok = True
    for key, chk in fin["checks"]["balance_identity"].items():
        lhs = chk["lhs"]
        rhs = chk["rhs"]
        ok = chk["ok"]
        all_ok &= bool(ok)
        mark = "✅" if ok else "❌"
        lhs_s = f"{lhs:,.0f}" if lhs else "缺失"
        rhs_s = f"{rhs:,.0f}" if rhs else "缺失"
        print(f"    {mark} {key:6}: 资产总计 {lhs_s}  ==  负债+权益 {rhs_s}  (diff={chk['diff']})")

    print(f"\n✅ 已落盘 {out_path}")
    if not all_ok:
        print("⚠️  恒等式未通过，请检查解析（可能抓到母公司表 / 科目定位错 / 单位不一致）", file=sys.stderr)
        return 2
    print("✅ 恒等式通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
