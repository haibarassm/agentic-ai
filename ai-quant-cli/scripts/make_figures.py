#!/usr/bin/env python3
"""L2 出图入口：读 data/parsed/financials_<code>.json → build/figures/*.png + manifest.json。

用法：
    python scripts/make_figures.py [--code 300750]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

from ai_quant.viz.charts import render_all_figures, setup_chinese_font  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="L2 出图")
    ap.add_argument("--code", default=None, help="股票代码（定位 data/parsed/financials_<code>.json）")
    ap.add_argument("--parsed-dir", default="data/parsed")
    ap.add_argument("--out-dir", default="build/figures")
    args = ap.parse_args()

    parsed_dir = Path(args.parsed_dir)
    if args.code:
        src = parsed_dir / f"financials_{args.code}.json"
    else:
        files = sorted(parsed_dir.glob("financials_*.json"))
        if not files:
            print("❌ data/parsed/ 下没有 financials_*.json，先跑 parse_report.py", file=sys.stderr)
            return 1
        src = files[-1]
    if not src.exists():
        print(f"❌ 找不到 {src}", file=sys.stderr)
        return 1

    fin = json.loads(src.read_text(encoding="utf-8"))
    font = setup_chinese_font()
    print(f"==> 出图 {src.name}（中文字体: {font or '未找到，可能乱码'}）")
    manifest = render_all_figures(fin, out_dir=args.out_dir)
    print(f"✅ 渲染 {len(manifest)} 张图 → {args.out_dir}/")
    for m in manifest:
        print(f"   - {m['id']}: {m['title']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
