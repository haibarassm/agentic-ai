#!/usr/bin/env python3
"""CLI：结构化数据 + 研判 → build/figures/*.png（L2 出图层入口）。

读 data/parsed/financials.json 与 analysis/findings.json，渲染图表与 manifest.json。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_quant.viz.charts import render_all  # noqa: E402


def main() -> int:
    chosen, manifest = render_all()
    print(f"[出图] 中文字体：{chosen}")
    for m in manifest:
        print(f"  ✓ {m['id']:<20} {m['path']}")
    print(f"[完成] {len(manifest)} 张图 + manifest.json → build/figures/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
