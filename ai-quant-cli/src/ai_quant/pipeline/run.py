"""L5 编排层：一键重跑整条流程。

硬约束：L1 最先、L3 最后；中间 L2 出图与 L4 研判并行。L4 研判是人工产出的
analysis/findings.json（非脚本），编排无法自动跑它——进 L3 前做闸门检查：
findings.json 缺失或不完整就明确提示并停下，不静默出半成品报告。

流程：
    L1 解析(PDF → financials.json)
      → L2 出图(financials + findings → figures/*.png)         ┐ 二者无依赖
      → [闸门] 检查 L4 研判产物 analysis/findings.json 是否就位  ┘
      → L3 报告(financials + findings + figures → report.html)
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PARSED = ROOT / "data" / "parsed" / "financials.json"


class PipelineError(RuntimeError):
    pass


def _log(step, msg):
    print(f"  [{step}] {msg}")


def _gate_check_findings(stock_code: str) -> dict:
    """L4 闸门：按股票代码定位研判产物，必须就位且结构完整，否则停下。"""
    from ai_quant.common import findings_path

    fp = findings_path(stock_code, ROOT)
    if not fp.exists():
        expected = f"analysis/findings_{stock_code}.json" if stock_code else "analysis/findings.json"
        raise PipelineError(
            f"研判产物缺失：找不到 {expected}\n"
            "  L4 风险研判由分析者（Claude Code）人工产出，按公司存为 analysis/findings_<代码>.json，不是脚本自动生成。\n"
            f"  请先为该公司（代码 {stock_code or '未知'}）完成研判并落盘，再重跑本编排。"
        )
    try:
        data = json.loads(fp.read_text("utf-8"))
    except json.JSONDecodeError as e:
        raise PipelineError(f"研判产物不是合法 JSON：{e}")
    missing = [k for k in ("risk_findings", "cross_checks") if not data.get(k)]
    if missing:
        raise PipelineError(f"研判产物缺少必需字段：{missing}")
    return data


def run_pipeline(pdf_path: str, skip_figures: bool = False, stock_code: str = "") -> dict:
    """一键跑完 解析 → 出图 → 闸门 → 报告，返回各阶段产物路径与计时。"""
    sys.path.insert(0, str(ROOT / "src"))
    from ai_quant.parsing.extract import extract_financials
    from ai_quant.viz.charts import render_all
    from ai_quant.report.build import build_report

    pdf = Path(pdf_path)
    if not pdf.exists():
        raise PipelineError(f"找不到年报 PDF：{pdf}")

    result = {}
    t0 = time.time()

    # ---- L1 解析 ----
    print("▶ L1 解析")
    data = extract_financials(str(pdf), stock_code=stock_code)
    PARSED.parent.mkdir(parents=True, exist_ok=True)
    PARSED.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    st = data["statements"]
    ok = data["checks"]["balance_identity"]["ok"]
    _log("L1", f"三表科目 {len(st['balance_sheet'])}/{len(st['income'])}/{len(st['cash_flow'])}"
               f"，会计恒等式自检 {'✓ 通过' if ok else '✗ 不平'}")
    if not ok:
        raise PipelineError("会计恒等式自检未通过，疑似解析错误，已中止。请检查 L1 解析。")
    result["financials"] = str(PARSED)

    # ---- L2 出图（与 L4 研判逻辑上并行；研判已离线完成）----
    if skip_figures:
        print("▶ L2 出图（跳过）")
    else:
        print("▶ L2 出图")
        chosen, manifest = render_all()
        _log("L2", f"中文字体 {chosen}，生成 {len(manifest)} 张图 → build/figures/")
        result["figures"] = len(manifest)

    # ---- L4 闸门 ----
    print("▶ L4 研判闸门")
    from ai_quant.common import findings_path
    code = data["meta"].get("stock_code", "")
    finds = _gate_check_findings(code)
    fp = findings_path(code, ROOT)
    n2 = len(finds.get("cross_checks_round2", []))
    _log("L4", f"{fp.name} 就位：风险 {len(finds['risk_findings'])} 条、"
               f"勾稽 {len(finds['cross_checks'])}+{n2} 条 ✓")
    result["findings"] = str(fp)

    # ---- L3 报告 ----
    print("▶ L3 报告")
    out = build_report()
    _log("L3", f"{out.name}（{out.stat().st_size/1024:.0f} KB，图表内嵌）")
    result["report"] = str(out)

    result["elapsed_sec"] = round(time.time() - t0, 1)
    print(f"\n✅ 全流程完成，用时 {result['elapsed_sec']}s")
    print(f"   打开报告： open '{out}'")

    # 列出最近若干份报告，方便对比历史（不覆盖）
    reports = sorted((ROOT / "reports").glob("report_*.html"), key=lambda p: p.stat().st_mtime, reverse=True)
    if len(reports) > 1:
        print(f"   reports/ 现有 {len(reports)} 份历史报告，最近 5 份：")
        for p in reports[:5]:
            print(f"     - {p.name}")
    return result
