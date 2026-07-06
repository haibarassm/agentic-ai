"""L3 报告汇编：financials + findings + figures → 自包含 HTML（图片 base64 内嵌）。

数据契约（铁律的体现）：
- 这一层只做「确定性汇编」，不做任何研判。
- findings 由 L4（Claude Code 人工）产出，本层只渲染。
- 图片 base64 内嵌 → 单文件 HTML，可离线分发、可放 CDN。

视图模型约定：
- 所有金额统一展示成「亿元」（源数据是千元），用 ``_yi`` 过滤器在模板里转换。
- summary.rows 已在 Python 端预算好字符串，避免模板里做条件判断。
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..common import to_yi

_HERE = Path(__file__).resolve().parent

# 报表 → 优先展示的关键科目（期末 vs 期初快照用）。
_SNAPSHOT_ITEMS: list[tuple[str, str]] = [
    ("income", "营业收入"),
    ("income", "归属于母公司所有者的净利润"),
    ("cash_flow", "经营活动产生的现金流量净额"),
    ("cash_flow", "投资活动产生的现金流量净额"),
    ("balance_sheet", "资产总计"),
    ("balance_sheet", "负债合计"),
    ("balance_sheet", "所有者权益合计"),
    ("balance_sheet", "归属于母公司所有者权益合计"),
    ("balance_sheet", "存货"),
    ("balance_sheet", "应收账款"),
    ("balance_sheet", "固定资产"),
    ("balance_sheet", "货币资金"),
]

_SEV_LABEL = {"high": "高风险", "medium": "中风险", "low": "低/正向"}
_VERDICT_LABEL = {"pass": "通过", "warn": "关注", "fail": "异常"}


def _yi_str(value: float | None) -> str:
    """千元 → 亿元字符串，None → '—'。"""
    if value is None:
        return "—"
    return f"{to_yi(value):,.2f}"


def _delta_str(curr: float | None, prior: float | None) -> str:
    """期末 vs 期初 变动率（保留符号）。"""
    if curr is None or prior is None or prior == 0:
        return "—"
    return f"{(curr - prior) / abs(prior) * 100:+.1f}%"


def _embed_image(fig_path: Path) -> str:
    """PNG → data URL。"""
    data = fig_path.read_bytes()
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:image/png;base64,{b64}"


def _build_summary_view(summary: dict) -> dict:
    """summary_history → {periods, rows[(label, [vals])], unit_label}，金额转亿元。"""
    periods = summary.get("periods", [])
    series = summary.get("series", {})
    # 大金额类（千元）→ 亿元；比率类（ROE）/每股（元）保持原义。
    ratio_keys = {"加权平均净资产收益率"}
    eps_keys = {"基本每股收益", "稀释每股收益"}
    rows: list[tuple[str, list[str]]] = []
    for label, vals in series.items():
        if not isinstance(vals, list):
            continue
        if label in ratio_keys:
            row = [f"{v * 100:.2f}%" if v is not None else "—" for v in vals]
        elif label in eps_keys:
            row = [f"{v:.2f}" if v is not None else "—" for v in vals]
        else:
            row = [_yi_str(v) for v in vals]
        rows.append((label, row))
    return {"periods": periods, "rows": rows, "unit_label": "亿元 / % / 元·股(见列)"}


def _build_snapshot_view(statements: dict) -> list[dict]:
    """挑关键科目做 期末 vs 期初 快照。"""
    out = []
    for stmt_name, item in _SNAPSHOT_ITEMS:
        seg = statements.get(stmt_name, {}).get(item)
        if seg is None:
            continue
        curr = seg.get("current")
        prior = seg.get("prior")
        out.append({
            "statement": stmt_name, "item": item,
            "current": _yi_str(curr), "prior": _yi_str(prior),
            "delta": _delta_str(curr, prior),
        })
    return out


def build_report(financials: dict, findings: dict, figures_manifest: list[dict],
                 out_path: str | Path, base_dir: str | Path,
                 generated_at: str = "") -> Path:
    """汇编 HTML 报告。

    Args:
        financials: data/parsed/financials_<code>.json 的内容。
        findings:   analysis/findings_<code>.json 的内容。
        figures_manifest: build/figures/manifest.json（每项含 path/title/caption）。
        out_path:   输出 HTML 路径。
        base_dir:   项目根，用于解析 manifest 里 figure 的相对路径。
        generated_at: 报告生成时间戳（字符串）。
    """
    base_dir = Path(base_dir)
    env = Environment(loader=FileSystemLoader(str(_HERE)),
                      autoescape=select_autoescape(["html"]))

    def format_value(v: Any) -> str:
        """模板过滤器：千元 → 亿元；字符串/None 原样。"""
        if v is None:
            return "—"
        if isinstance(v, (int, float)):
            return _yi_str(float(v))
        return str(v)

    env.filters["format_value"] = format_value
    env.globals["format_value"] = format_value  # 模板里既可 {{ v|format_value }} 也可 {{ format_value(v) }}

    # 图片 base64 内嵌
    figures = []
    for m in figures_manifest:
        fig_path = (base_dir / m["path"]).resolve()
        if not fig_path.exists():
            continue
        figures.append({
            "title": m.get("title", ""),
            "caption": m.get("caption", ""),
            "data_url": _embed_image(fig_path),
        })

    meta = financials.get("meta", {})
    checks = financials.get("checks", {}).get("balance_identity", {})

    ctx = {
        "meta": {
            "company": meta.get("company", ""),
            "stock_code": meta.get("stock_code", ""),
            "period": meta.get("period", ""),
            "currency": meta.get("currency", "CNY"),
            "unit": meta.get("unit", "千元"),
            "source_pdf": meta.get("source_pdf", ""),
            "parsed_at": meta.get("parsed_at", ""),
        },
        "findings": findings,
        "figures": figures,
        "summary": _build_summary_view(financials.get("summary_history", {})),
        "snapshot": _build_snapshot_view(financials.get("statements", {})),
        "checks": {
            "current": checks.get("current", {}),
            "prior": checks.get("prior", {}),
        },
        "sev_label": _SEV_LABEL,
        "verdict_label": _VERDICT_LABEL,
        "generated_at": generated_at,
    }

    tmpl = env.get_template("template.html")
    html = tmpl.render(**ctx)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return out_path


def load_json(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))
