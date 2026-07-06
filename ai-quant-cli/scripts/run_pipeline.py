#!/usr/bin/env python3
"""L5 流水线入口：L1 解析 → L2 出图 → 【L4 闸门】→ L3 汇编。

用法：
    python scripts/run_pipeline.py --code 300750                # 全流程（需 PDF）
    python scripts/run_pipeline.py --code 300750 --pdf data/xxx.pdf
    python scripts/run_pipeline.py --code 300750 --skip-parse --skip-figures   # 只补 L3（findings 已就位）

铁律：L4 风险研判（findings_<code>.json）必须由 Claude Code 人工产出。
      闸门未过则停在 L3 之前，exit code 2，绝不静默出半成品报告。
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

from ai_quant.pipeline.run import L4GateError, run_pipeline  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="ai-quant-cli 全流水线")
    ap.add_argument("--code", default="300750", help="股票代码（默认 300750 宁德时代）")
    ap.add_argument("--pdf", default=None, help="年报 PDF 路径（不指定则在 data/ 下按 code 查找）")
    ap.add_argument("--skip-parse", action="store_true", help="复用已有 financials，跳过 L1")
    ap.add_argument("--skip-figures", action="store_true", help="复用已有 figures，跳过 L2")
    args = ap.parse_args()

    ts = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")
    print(f"=== ai-quant-cli 流水线启动  code={args.code}  ts={ts} ===\n")

    try:
        result = run_pipeline(
            code=args.code,
            root_dir=_ROOT,
            pdf_path=args.pdf,
            skip_parse=args.skip_parse,
            skip_figures=args.skip_figures,
            generated_at=ts,
        )
    except L4GateError as e:
        print(f"\n❌ 流水线在 L4 闸门停下（这是设计内的安全行为）：\n{e}", file=sys.stderr)
        return 2
    except FileNotFoundError as e:
        print(f"\n❌ 缺少必要文件：{e}", file=sys.stderr)
        return 1

    print(f"\n=== 流水线完成 ===")
    print(f"  financials: {result.financials_path.relative_to(_ROOT)}")
    print(f"  figures:    {result.figures_dir.relative_to(_ROOT)}/")
    print(f"  findings:   {result.findings_path.relative_to(_ROOT)}")
    if result.report_path:
        print(f"  report:     {result.report_path.relative_to(_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
