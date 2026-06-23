#!/usr/bin/env python3
"""CLI：一键重跑整条流程（L5 编排层入口）。

    python scripts/run_pipeline.py data/<年报>.pdf [--skip-figures]

跑完 解析 → 出图 →（L4 研判闸门）→ 报告。L4 研判产物 analysis/findings.json
由分析者人工产出；闸门检查它是否就位，缺失则明确提示并停下。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_quant.pipeline.run import run_pipeline, PipelineError  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="AI Quant CLI 一键端到端")
    ap.add_argument("pdf", nargs="?", default=str(ROOT / "data" / "宁德时代2025年年度报告.pdf"),
                    help="年报 PDF 路径（默认用 data/ 下的宁德时代年报）")
    ap.add_argument("--skip-figures", action="store_true", help="跳过出图，仅解析+报告")
    ap.add_argument("--code", default="", help="股票代码（年报封面无法识别时显式指定，如 002594）")
    args = ap.parse_args()

    print("=" * 56)
    print(f"AI Quant CLI · 端到端：{Path(args.pdf).name}")
    print("=" * 56)
    try:
        run_pipeline(args.pdf, skip_figures=args.skip_figures, stock_code=args.code)
    except PipelineError as e:
        print(f"\n✗ 流程中止：{e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
