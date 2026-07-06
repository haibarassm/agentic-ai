#!/usr/bin/env python3
"""L3 报告汇编入口：financials + findings + figures → build/reports/report_<code>_<period>_<ts>.html。

用法：
    python scripts/build_report.py [--code 300750]

前置：
    - data/parsed/financials_<code>.json（L1 产出）
    - analysis/findings_<code>.json（L4 人工产出 —— 缺则报错，绝不静默出半成品）
    - build/figures/manifest.json + *.png（L2 产出）
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

from ai_quant.report.build import build_report  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="L3 报告汇编")
    ap.add_argument("--code", default=None, help="股票代码（定位 financials/findings）")
    ap.add_argument("--parsed-dir", default="data/parsed")
    ap.add_argument("--findings-dir", default="analysis")
    ap.add_argument("--figures-dir", default="build/figures")
    ap.add_argument("--out-dir", default="build/reports")
    args = ap.parse_args()

    parsed_dir = _ROOT / args.parsed_dir
    findings_dir = _ROOT / args.findings_dir
    figures_dir = _ROOT / args.figures_dir

    # 定位 financials
    if args.code:
        fin_path = parsed_dir / f"financials_{args.code}.json"
        code = args.code
    else:
        files = sorted(parsed_dir.glob("financials_*.json"))
        if not files:
            print("❌ data/parsed/ 下没有 financials_*.json，先跑 parse_report.py", file=sys.stderr)
            return 1
        fin_path = files[-1]
        code = fin_path.stem.replace("financials_", "")
    if not fin_path.exists():
        print(f"❌ 找不到 {fin_path}", file=sys.stderr)
        return 1

    # L4 闸门：findings 必须就位
    findings_path = findings_dir / f"findings_{code}.json"
    if not findings_path.exists():
        print(f"❌ L4 闸门未通过：缺少 {findings_path}", file=sys.stderr)
        print("   风险研判必须由 Claude Code 人工产出后才能汇编报告，拒绝出半成品。", file=sys.stderr)
        return 2

    manifest_path = figures_dir / "manifest.json"
    if not manifest_path.exists():
        print(f"❌ 缺少 {manifest_path}，先跑 make_figures.py", file=sys.stderr)
        return 1

    financials = json.loads(fin_path.read_text(encoding="utf-8"))
    findings = json.loads(findings_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    period = financials.get("meta", {}).get("period", "unknown")
    ts = datetime.now(timezone(timedelta(hours=8))).strftime("%Y%m%d_%H%M")
    out_path = _ROOT / args.out_dir / f"report_{code}_{period}_{ts}.html"

    print(f"==> 汇编报告 {code} 期 {period}")
    print(f"   financials: {fin_path.relative_to(_ROOT)}")
    print(f"   findings:   {findings_path.relative_to(_ROOT)}")
    print(f"   figures:    {len(manifest)} 张")
    build_report(financials, findings, manifest, out_path, base_dir=_ROOT,
                 generated_at=datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"))
    print(f"✅ 报告已生成：{out_path.relative_to(_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
