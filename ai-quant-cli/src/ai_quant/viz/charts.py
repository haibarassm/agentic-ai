"""L2 出图：matplotlib 渲染趋势/结构图，处理中文字体与负号。

渲染约定（踩坑后默认遵守）：
- 后端 Agg（无界面直接出 PNG）。
- 中文字体回退链：挑本机第一个可用 CJK 字体。
- axes.unicode_minus=False（负号否则变方框；本项目有大量负值）。
- 金额统一换算成「亿元」更易读（源数据是千元）。
- 产出 build/figures/*.png + manifest.json（report 层按 id 内嵌）。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.font_manager as fm  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

from ..common import to_yi  # noqa: E402

# 配色
C_PRIMARY = "#1f4e79"   # 深蓝主色
C_WARN = "#c00000"      # 警示红（负值/风险）
C_GOOD = "#2e7d32"      # 正向绿
C_PRIOR = "#a6c8e0"     # 上期浅蓝
C_GREY = "#7f7f7f"      # 中性灰

# 中文字体回退链（跨平台：Windows/macOS/Linux 都覆盖）
_CJK_CANDIDATES = [
    "Microsoft YaHei", "SimHei", "SimSun",  # Windows
    "PingFang SC", "Hiragino Sans GB", "Arial Unicode MS", "Heiti SC",  # macOS
    "Noto Sans CJK SC", "Source Han Sans SC", "WenQuanYi Zen Hei",  # Linux
]

_FONT_SETUP = False


def setup_chinese_font() -> str:
    """挑本机第一个可用的 CJK 字体，写进 rcParams。返回字体名（找不到返回空）。"""
    global _FONT_SETUP
    available = {f.name for f in fm.fontManager.ttflist}
    chosen = ""
    for name in _CJK_CANDIDATES:
        if name in available:
            chosen = name
            break
    if not chosen:
        # 退而求其次：任何名字含 CJK 关键词的
        for f in fm.fontManager.ttflist:
            if any(k in f.name for k in ("Hei", "Song", "Kai", "Yuan", "CJK", "SC")):
                chosen = f.name
                break
    plt.rcParams["font.sans-serif"] = ([chosen] if chosen else []) + plt.rcParams["font.sans-serif"]
    plt.rcParams["axes.unicode_minus"] = False
    _FONT_SETUP = True
    return chosen


def _yi(value_kilo: float | None) -> float | None:
    return to_yi(value_kilo)


def _period_labels(periods: list[str]) -> list[str]:
    return [f"{p}" for p in periods]


def _save(fig, out_dir: Path, fig_id: str, title: str, caption: str, manifest: list[dict]) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{fig_id}.png"
    fig.tight_layout()
    fig.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)
    manifest.append({"id": fig_id, "path": str(path.relative_to(out_dir.parent.parent)).replace("\\", "/"),
                     "title": title, "caption": caption})
    return path


def _chart_revenue_profit(summary: dict, out_dir: Path, manifest: list) -> None:
    series = summary.get("series", {})
    periods = _period_labels(summary.get("periods", []))
    rev = series.get("营业收入")
    ni = series.get("归属于母公司所有者的净利润")
    if not periods or rev is None:
        return
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(periods, [_yi(v) for v in rev], "-o", color=C_PRIMARY, linewidth=2.2, label="营业收入")
    if ni is not None:
        ax.plot(periods, [_yi(v) for v in ni], "-s", color=C_WARN, linewidth=2.2, label="归母净利润")
    ax.set_title("营业收入与归母净利润趋势")
    ax.set_ylabel("亿元")
    ax.legend(loc="best", framealpha=0.9)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    _save(fig, out_dir, "revenue_profit", "营收与归母净利润",
          "多年趋势（路A：年报内嵌主要会计数据）。单位：亿元。", manifest)


def _chart_profitability(summary: dict, out_dir: Path, manifest: list) -> None:
    series = summary.get("series", {})
    periods = _period_labels(summary.get("periods", []))
    rev = series.get("营业收入")
    ni = series.get("归属于母公司所有者的净利润")
    roe = series.get("加权平均净资产收益率")
    if not periods or rev is None or ni is None:
        return
    net_margin = [(_yi(n) / _yi(r) * 100) if r else None for r, n in zip(rev, ni)]
    fig, ax1 = plt.subplots(figsize=(7, 4))
    ax1.plot(periods, net_margin, "-o", color=C_PRIMARY, linewidth=2.2, label="净利率(归母/营收)")
    ax1.set_ylabel("净利率 %", color=C_PRIMARY)
    ax1.tick_params(axis="y", labelcolor=C_PRIMARY)
    ax1.grid(axis="y", linestyle="--", alpha=0.4)
    if roe is not None:
        ax2 = ax1.twinx()
        ax2.plot(periods, [v * 100 if v is not None else v for v in roe], "--s", color=C_GOOD, linewidth=2, label="ROE")
        ax2.set_ylabel("ROE %", color=C_GOOD)
        ax2.tick_params(axis="y", labelcolor=C_GOOD)
    ax1.set_title("盈利质量：净利率与 ROE")
    _save(fig, out_dir, "profitability", "净利率与ROE",
          "净利率=归母净利润/营业收入；ROE=加权平均净资产收益率。", manifest)


def _chart_ocf_vs_ni(summary: dict, out_dir: Path, manifest: list) -> None:
    series = summary.get("series", {})
    periods = _period_labels(summary.get("periods", []))
    ocf = series.get("经营活动产生的现金流量净额")
    ni = series.get("归属于母公司所有者的净利润")
    if not periods or ocf is None or ni is None:
        return
    x = range(len(periods))
    width = 0.38
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar([i - width / 2 for i in x], [_yi(v) for v in ocf], width, color=C_PRIMARY, label="经营现金流净额")
    ax.bar([i + width / 2 for i in x], [_yi(v) for v in ni], width, color=C_WARN, label="归母净利润")
    ax.set_xticks(list(x))
    ax.set_xticklabels(periods)
    ax.set_title("经营现金流 vs 归母净利润")
    ax.set_ylabel("亿元")
    ax.legend(loc="best", framealpha=0.9)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    _save(fig, out_dir, "ocf_vs_ni", "现金流 vs 净利润",
          "经营现金流长期低于净利润是盈利质量警示信号。单位：亿元。", manifest)


def _chart_balance_structure(statements: dict, out_dir: Path, manifest: list) -> None:
    bs = statements.get("balance_sheet", {})
    periods = ["期末", "期初"]
    liab = [bs.get("负债合计", {}).get("current"), bs.get("负债合计", {}).get("prior")]
    eq_parent = [bs.get("归属于母公司所有者权益合计", {}).get("current"),
                 bs.get("归属于母公司所有者权益合计", {}).get("prior")]
    eq_minor = [bs.get("少数股东权益", {}).get("current"), bs.get("少数股东权益", {}).get("prior")]
    if liab[0] is None:
        return
    fig, ax = plt.subplots(figsize=(6.5, 4))
    x = range(len(periods))
    width = 0.5
    ax.bar(list(x), [(_yi(v) or 0) for v in liab], width, color=C_WARN, label="负债合计")
    bottoms = [(_yi(v) or 0) for v in liab]
    ax.bar(list(x), [(_yi(v) or 0) for v in eq_parent], width, bottom=bottoms,
           color=C_PRIMARY, label="归母权益")
    bottoms2 = [b + ((_yi(ep) or 0)) for b, ep in zip(bottoms, eq_parent)]
    ax.bar(list(x), [(_yi(v) or 0) for v in eq_minor], width, bottom=bottoms2,
           color=C_GOOD, label="少数股东权益")
    ax.set_xticks(list(x))
    ax.set_xticklabels(periods)
    ax.set_title("资产负债结构（负债 + 权益）")
    ax.set_ylabel("亿元")
    ax.legend(loc="best", framealpha=0.9, fontsize=9)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    _save(fig, out_dir, "balance_structure", "资产负债结构",
          "期末/期初对比：负债与所有者权益构成。单位：亿元。", manifest)


def _chart_cashflow_three(statements: dict, out_dir: Path, manifest: list) -> None:
    """三大活动现金流净额（经营/投资/筹资），期末 vs 期初。

    用子串匹配定位科目（不同公司命名带乱码尾巴，如『投资活动使用的现金流量净额))』）。
    """
    cf = statements.get("cash_flow", {})
    labels = ["经营活动", "投资活动", "筹资活动"]
    needles = ["经营活动", "投资活动", "筹资活动"]

    def find_net(needle: str) -> tuple[float | None, float | None]:
        for k, v in cf.items():
            if needle in k and "净额" in k:
                return v.get("current"), v.get("prior")
        return None, None

    current, prior = [], []
    for n in needles:
        c, p = find_net(n)
        current.append(c); prior.append(p)
    if current[0] is None:  # 经营活动都没有就不出图
        return
    # 投资活动『使用的现金流量净额』按惯例是负值（净流出），若原值>0 则取负
    def norm_neg(v, idx):
        if v is None:
            return None
        return -v if (idx == 1 and v > 0) else v

    current = [norm_neg(v, i) for i, v in enumerate(current)]
    prior = [norm_neg(v, i) for i, v in enumerate(prior)]
    x = range(len(labels))
    width = 0.38
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar([i - width / 2 for i in x], [(_yi(v) or 0) for v in current], width, color=C_PRIMARY, label="期末")
    ax.bar([i + width / 2 for i in x], [(_yi(v) or 0) for v in prior], width, color=C_PRIOR, label="期初")
    ax.axhline(0, color=C_GREY, linewidth=0.8)
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels)
    ax.set_title("三大活动现金流量净额")
    ax.set_ylabel("亿元")
    ax.legend(loc="best", framealpha=0.9)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    _save(fig, out_dir, "cashflow_three", "三大活动现金流",
          "经营/投资/筹资活动现金流量净额，期末 vs 期初。单位：亿元。", manifest)


def render_all_figures(financials: dict[str, Any], out_dir: str | Path = "build/figures") -> list[dict]:
    """渲染全部图表到 out_dir，返回 manifest（同时写 manifest.json）。"""
    if not _FONT_SETUP:
        setup_chinese_font()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest: list[dict] = []

    summary = financials.get("summary_history", {})
    statements = financials.get("statements", {})

    _chart_revenue_profit(summary, out_dir, manifest)
    _chart_profitability(summary, out_dir, manifest)
    _chart_ocf_vs_ni(summary, out_dir, manifest)
    _chart_balance_structure(statements, out_dir, manifest)
    _chart_cashflow_three(statements, out_dir, manifest)

    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest
