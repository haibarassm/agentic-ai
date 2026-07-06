"""L5 流水线编排：L1 解析 → (L2 出图 ∥ L4 人工研判) → L3 汇编。

DAG：
    PDF ──L1──▶ financials_<code>.json ──┬──▶ L2 figures (build/figures)
                                         │
                                         ├──▶ L4 人工研判 (analysis/findings_<code>.json)  ← 人工产物，不在脚本里
                                         │
                                         └──▶ 【L4 闸门】findings 就位？
                                                  ├ 是 → L3 汇编 → report_<code>_<period>_<ts>.html
                                                  └ 否 → 报错停下，绝不静默出半成品报告

铁律：L4 风险研判由 Claude Code 人工产出，本模块不调任何大模型 API。
本模块只做编排与确定性计算（解析/出图/汇编），并守好 L4 闸门。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ..parsing.extract import extract_financials
from ..viz.charts import render_all_figures
from ..report.build import build_report

# 可跳过的阶段名（用于 --skip-*）。
STAGE_PARSE = "parse"
STAGE_FIGURES = "figures"


class L4GateError(RuntimeError):
    """L4 人工研判产物缺失，拒绝汇编报告。"""


@dataclass
class PipelineResult:
    financials_path: Path
    figures_dir: Path
    findings_path: Path
    report_path: Path | None  # L4 闸门未过时为 None
    code: str
    period: str


def _find_pdf_for_code(data_dir: Path, code: str) -> Path | None:
    """按 code 猜测 PDF 文件名（data/<code>*.pdf 或 data/*<关键词>*.pdf）。"""
    candidates = sorted(data_dir.glob(f"*{code}*.pdf"))
    if candidates:
        return candidates[0]
    # 退化：data 下唯一一个 pdf
    all_pdf = sorted(data_dir.glob("*.pdf"))
    if len(all_pdf) == 1:
        return all_pdf[0]
    return None


def run_pipeline(
    *,
    code: str,
    root_dir: str | Path,
    pdf_path: str | Path | None = None,
    skip_parse: bool = False,
    skip_figures: bool = False,
    generated_at: str = "",
) -> PipelineResult:
    """跑完整流水线。

    Args:
        code: 股票代码（定位 financials/findings/report）。
        root_dir: 项目根。
        pdf_path: 年报 PDF 路径（skip_parse=False 时必需）。
        skip_parse: 复用已存在的 financials_<code>.json，跳过 L1。
        skip_figures: 跳过 L2 出图（复用已有 build/figures）。
        generated_at: 报告时间戳。
    """
    root = Path(root_dir)
    parsed_dir = root / "data" / "parsed"
    figures_dir = root / "build" / "figures"
    reports_dir = root / "build" / "reports"
    findings_dir = root / "analysis"
    parsed_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    financials_path = parsed_dir / f"financials_{code}.json"
    findings_path = findings_dir / f"findings_{code}.json"
    manifest_path = figures_dir / "manifest.json"

    # ---- L1 解析 ----
    if skip_parse:
        if not financials_path.exists():
            raise FileNotFoundError(f"--skip-parse 但 {financials_path} 不存在")
        print(f"[L1] skip，复用 {financials_path.relative_to(root)}")
        fin = json.loads(financials_path.read_text(encoding="utf-8"))
    else:
        if pdf_path is None:
            pdf_path = _find_pdf_for_code(root / "data", code)
        if pdf_path is None or not Path(pdf_path).exists():
            raise FileNotFoundError(f"找不到 {code} 对应的 PDF，请用 --pdf 指定")
        print(f"[L1] 解析 {Path(pdf_path).name} ...")
        fin = extract_financials(Path(pdf_path), stock_code=code)
        financials_path.write_text(json.dumps(fin, ensure_ascii=False, indent=2), encoding="utf-8")
        code = fin["meta"]["stock_code"] or code
        # code 可能因解析被校正，重新定位 findings 路径
        findings_path = findings_dir / f"findings_{code}.json"
        financials_path = parsed_dir / f"financials_{code}.json"
        if not financials_path.exists():
            financials_path.write_text(json.dumps(fin, ensure_ascii=False, indent=2), encoding="utf-8")

    # 恒等式自检（L1 内置，这里只汇报）
    chk = fin.get("checks", {}).get("balance_identity", {})
    cur_ok = chk.get("current", {}).get("ok", False)
    pri_ok = chk.get("prior", {}).get("ok", False)
    print(f"[L1] 恒等式自检：期末 {'✅' if cur_ok else '❌'}  期初 {'✅' if pri_ok else '❌'}")

    period = fin.get("meta", {}).get("period", "unknown")

    # ---- L2 出图 ----
    if skip_figures:
        print(f"[L2] skip，复用 {figures_dir.relative_to(root)}")
    else:
        print(f"[L2] 出图 → {figures_dir.relative_to(root)}/")
        manifest = render_all_figures(fin, out_dir=figures_dir)
        print(f"[L2] 渲染 {len(manifest)} 张图")

    # ---- L4 闸门 ----
    if not findings_path.exists():
        msg = (f"L4 闸门未通过：缺少 {findings_path.relative_to(root)}。\n"
               f"L1/L2 已完成，但风险研判（findings）必须由 Claude Code 人工产出后才能汇编报告。\n"
               f"拒绝静默出半成品报告。请补齐 findings 后重跑（可加 --skip-parse --skip-figures）。")
        print(f"[L4] ❌ {msg}", flush=True)
        raise L4GateError(msg)
    print(f"[L4] ✅ 闸门通过：{findings_path.relative_to(root)}")
    findings = json.loads(findings_path.read_text(encoding="utf-8"))

    # ---- L3 汇编 ----
    if not manifest_path.exists():
        raise FileNotFoundError(f"缺少 {manifest_path}，L2 未产出")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    report_path = reports_dir / f"report_{code}_{period}_{_safe_ts(generated_at)}.html"
    print(f"[L3] 汇编报告 → {report_path.relative_to(root)}")
    build_report(fin, findings, manifest, report_path, base_dir=root, generated_at=generated_at)
    print(f"[L3] ✅ 完成")

    return PipelineResult(
        financials_path=financials_path,
        figures_dir=figures_dir,
        findings_path=findings_path,
        report_path=report_path,
        code=code,
        period=period,
    )


def _safe_ts(generated_at: str) -> str:
    """从 ISO 时间戳里取 yyyymmdd_hhmm 做文件名；空则返回 'manual'。"""
    if not generated_at:
        return "manual"
    # 形如 2026-07-06T13:59:00+08:00 → 20260706_1359
    try:
        date_part = generated_at[:10].replace("-", "")
        time_part = generated_at[11:16].replace(":", "")
        return f"{date_part}_{time_part}"
    except Exception:
        return "manual"
