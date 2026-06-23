"""L2 出图层：读 financials.json + findings.json，渲染趋势/结构图。

中文字体（阶段 4 实测落定）：matplotlib 默认无中文字体会乱码（缺字变方框）。
本模块用一个回退链挑第一个本机可用的 CJK 字体，并关掉 unicode_minus
（否则负号渲染成方框）。macOS 上 PingFang SC / Hiragino Sans GB / Arial
Unicode MS / Heiti SC 至少有一个在。

产出：build/figures/*.png + build/figures/manifest.json（report 层按 id 内嵌）。
金额一律由千元换算为「亿元」展示（÷1e5），更易读。
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # 无界面后端，直接出 PNG
import matplotlib.pyplot as plt
from matplotlib import font_manager

from ai_quant.common import findings_path, val

ROOT = Path(__file__).resolve().parents[3]
FIG_DIR = ROOT / "build" / "figures"

# 中文字体回退链：优先黑体类无衬线
_FONT_PREFERENCE = [
    "PingFang SC",
    "Hiragino Sans GB",
    "Arial Unicode MS",
    "Heiti SC",
    "Songti SC",
    "STHeiti",
]

# 专业、克制的配色
C_PRIMARY = "#1f4e79"   # 深蓝
C_ACCENT = "#c00000"    # 警示红
C_GREEN = "#2e7d32"
C_GRAY = "#7f7f7f"
C_PRIOR = "#a6c8e0"     # 上期浅蓝
C_CUR = "#1f4e79"       # 本期深蓝
C_POS = "#2e7d32"
C_NEG = "#c00000"

YI = 1e5  # 千元 → 亿元


def setup_chinese_font() -> str:
    """挑第一个本机可用的中文字体并设进 rcParams，返回字体名。"""
    available = {f.name for f in font_manager.fontManager.ttflist}
    chosen = next((f for f in _FONT_PREFERENCE if f in available), None)
    if chosen is None:
        raise RuntimeError(
            "未找到可用中文字体，候选：" + "、".join(_FONT_PREFERENCE)
        )
    plt.rcParams["font.sans-serif"] = [chosen] + plt.rcParams.get("font.sans-serif", [])
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["axes.unicode_minus"] = False  # 负号正常显示，不变方框
    plt.rcParams["figure.dpi"] = 130
    plt.rcParams["savefig.bbox"] = "tight"
    return chosen


def _load():
    fin = json.loads((ROOT / "data" / "parsed" / "financials.json").read_text("utf-8"))
    fp = findings_path(fin["meta"].get("stock_code"), ROOT)
    finds = json.loads(fp.read_text("utf-8"))
    return fin, finds


def _bs(fin, name, period="current"):
    it = fin["statements"]["balance_sheet"].get(name)
    return it[period] if it else None


def _find(fin, stmt, sub, period="current"):
    for k, v in fin["statements"][stmt].items():
        if sub in k:
            return v[period]
    return None


def _save(fig, fid, title, caption, manifest):
    path = FIG_DIR / f"{fid}.png"
    fig.savefig(path)
    plt.close(fig)
    manifest.append(
        {"id": fid, "path": f"figures/{fid}.png", "title": title, "caption": caption}
    )


def _bar_labels(ax, bars, fmt="{:.0f}", dy=0):
    for b in bars:
        h = b.get_height()
        ax.annotate(
            fmt.format(h),
            (b.get_x() + b.get_width() / 2, h),
            ha="center",
            va="bottom" if h >= 0 else "top",
            fontsize=8,
            xytext=(0, 2 + dy if h >= 0 else -2 - dy),
            textcoords="offset points",
        )


# ---------------- 各图 ----------------

def chart_revenue_profit(fin, manifest):
    rev_c_raw = val(fin, "营业收入"); rev_p_raw = val(fin, "营业收入", "prior")
    rev_c = rev_c_raw / YI
    rev_p = rev_p_raw / YI
    ni_c = val(fin, "净利润") / YI
    ni_p = val(fin, "净利润", "prior") / YI
    cogs_c = val(fin, "营业成本")
    cogs_p = val(fin, "营业成本", "prior")
    gm_c = (rev_c_raw - cogs_c) / rev_c_raw * 100
    gm_p = (rev_p_raw - cogs_p) / rev_p_raw * 100
    nm_c = ni_c / rev_c * 100
    nm_p = ni_p / rev_p * 100

    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    x = [0, 1]
    w = 0.34
    b1 = ax.bar([i - w / 2 for i in x], [rev_p, rev_c], w, label="营业收入", color=[C_PRIOR, C_CUR])
    b2 = ax.bar([i + w / 2 for i in x], [ni_p, ni_c], w, label="净利润", color=["#f4b9b9", C_ACCENT])
    ax.set_xticks(x)
    ax.set_xticklabels(["2024", "2025"])
    ax.set_ylabel("金额（亿元）")
    _bar_labels(ax, list(b1) + list(b2), "{:.0f}")

    ax2 = ax.twinx()
    ax2.plot(x, [gm_p, gm_c], "o-", color=C_GREEN, lw=2, label="毛利率")
    ax2.plot(x, [nm_p, nm_c], "s--", color=C_GRAY, lw=2, label="净利率")
    ax2.set_ylabel("比率（%）")
    ax2.set_ylim(0, max(gm_c, nm_c) * 1.8)
    for xi, (g, n) in zip(x, [(gm_p, nm_p), (gm_c, nm_c)]):
        ax2.annotate(f"{g:.1f}%", (xi, g), color=C_GREEN, fontsize=8, xytext=(0, 6), textcoords="offset points", ha="center")
        ax2.annotate(f"{n:.1f}%", (xi, n), color=C_GRAY, fontsize=8, xytext=(0, -12), textcoords="offset points", ha="center")

    ax.set_title("营收与净利润：增长与盈利能力", fontweight="bold")
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="upper left", fontsize=8, ncol=2)
    _save(fig, "revenue_profit", "营收与净利润",
          "净利润+42%显著快于营收+17%，由毛利率提升与财务净收益驱动。", manifest)


def chart_ocf_bridge(fin, finds, manifest):
    """经营现金流构成瀑布图：净利润 → 各调节项 → 经营现金流。

    数据来自 findings['indirect_method_bridge']['waterfall']（人工研判时按公司预分桶），
    每项 {label, value(千元), type: start|add|sub|end}，因此本图对各公司通用、不写死科目。
    """
    br = finds.get("indirect_method_bridge", {})
    wf = br.get("waterfall")
    if not wf:
        return  # 无桥数据则跳过该图
    title = br.get("chart_title", "经营现金流构成拆解（瀑布图）")
    caption = br.get("chart_caption", "净利润经折旧/减值与营运资本变动桥接到经营活动现金流量净额。")

    fig, ax = plt.subplots(figsize=(9, 4.8))
    cum = 0.0
    xticks = []
    for i, step in enumerate(wf):
        v = step["value"] / YI
        typ = step["type"]
        xticks.append(step["label"])
        if typ in ("start", "end"):
            ax.bar(i, v, 0.6, color=C_PRIMARY)
            ax.annotate(f"{v:.0f}", (i, v), ha="center",
                        va="bottom" if v >= 0 else "top", fontsize=8, fontweight="bold")
            cum = v
        else:
            color = C_POS if v >= 0 else C_NEG
            ax.bar(i, v, 0.6, bottom=cum, color=color, alpha=0.9)
            ax.plot([i - 0.3, i - 0.7], [cum, cum], color=C_GRAY, lw=0.7, ls=":")
            sign = "+" if v >= 0 else ""
            ax.annotate(f"{sign}{v:.0f}", (i, cum + v + (1 if v >= 0 else -1)),
                        ha="center", va="bottom" if v >= 0 else "top", fontsize=8, color=color)
            cum += v
    ax.set_xticks(range(len(wf)))
    ax.set_xticklabels(xticks, fontsize=8.5)
    ax.set_ylabel("金额（亿元）")
    ax.axhline(0, color="black", lw=0.6)
    ax.set_title(title, fontweight="bold", color=C_ACCENT)
    _save(fig, "ocf_bridge", "经营现金流构成拆解（瀑布图）", caption, manifest)


def chart_inventory_structure(finds, manifest):
    """存货结构 期末vs期初（账面价值）。数据来自 findings['inventory_composition']
    （人工研判时从存货附注录入），每项 {name, current, prior}，对各公司通用。"""
    comp_list = finds.get("inventory_composition")
    if not comp_list:
        return  # 无存货结构数据则跳过该图
    labels = [c["name"] for c in comp_list]
    cur = [c["current"] / YI for c in comp_list]
    pri = [c["prior"] / YI for c in comp_list]
    comp = {c["name"]: (c["current"], c["prior"]) for c in comp_list}
    x = range(len(labels))
    w = 0.38
    fig, ax = plt.subplots(figsize=(7.6, 4.2))
    b1 = ax.bar([i - w / 2 for i in x], pri, w, label="期初(2024)", color=C_PRIOR)
    b2 = ax.bar([i + w / 2 for i in x], cur, w, label="期末(2025)", color=C_CUR)
    _bar_labels(ax, list(b1) + list(b2), "{:.0f}")
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels)
    ax.set_ylabel("账面价值（亿元）")
    ax.set_title(finds.get("inventory_title", "存货结构：期末 vs 期初（账面价值）"), fontweight="bold")
    ax.legend(fontsize=8)
    for i, k in enumerate(labels):
        g = comp[k][0] / comp[k][1] - 1
        ax.annotate(f"{g:+.0%}", (i, max(cur[i], pri[i])), ha="center", va="bottom",
                    fontsize=8, color=C_ACCENT if g > 0.3 else C_GRAY, xytext=(0, 12), textcoords="offset points")
    # 默认按数据生成图注：点出增幅最大的存货类目
    top = max(comp_list, key=lambda c: (c["current"] - c["prior"]) / c["prior"] if c["prior"] else 0)
    g_top = top["current"] / top["prior"] - 1 if top["prior"] else 0
    default_cap = f"按账面价值拆分存货：增量主要来自{top['name']}（同比 {g_top:+.0%}）。"
    _save(fig, "inventory_structure", "存货结构对比",
          finds.get("inventory_caption", default_cap), manifest)


def chart_growth_compare(fin, manifest):
    def gr(canonical):
        c = val(fin, canonical)
        p = val(fin, canonical, "prior")
        return None if (c is None or p in (None, 0)) else (c - p) / p * 100
    candidates = [
        ("营业收入", "营业收入"), ("净利润", "净利润"), ("经营现金流", "经营现金流"),
        ("应收账款", "应收账款"), ("存货", "存货"), ("资本开支", "资本开支"),
        ("合同负债", "合同负债"),
    ]
    items = [(lab, gr(c)) for lab, c in candidates]
    items = [(lab, v) for lab, v in items if v is not None]  # 缺科目则跳过
    labels = [i[0] for i in items]
    vals = [i[1] for i in items]
    colors = [C_ACCENT if v >= 50 else (C_PRIMARY if v >= 0 else C_GREEN) for v in vals]
    fig, ax = plt.subplots(figsize=(7.8, 4.2))
    bars = ax.bar(labels, vals, color=colors, width=0.6)
    _bar_labels(ax, bars, "{:+.0f}%")
    ax.axhline(0, color="black", lw=0.6)
    ax.set_ylabel("同比增速（%）")
    ax.set_title("关键指标同比增速", fontweight="bold")
    _save(fig, "growth_compare", "关键指标同比增速",
          "关键财务指标同比增速对比，红=高增(≥50%)、蓝=增长、绿=下降。", manifest)


def chart_balance_structure(fin, manifest):
    liab_c = val(fin, "负债合计") / YI
    liab_p = val(fin, "负债合计", "prior") / YI
    eq_c = val(fin, "所有者权益合计") / YI
    eq_p = val(fin, "所有者权益合计", "prior") / YI
    interest_c = ((val(fin, "短期借款") or 0) + (val(fin, "长期借款") or 0)) / YI

    fig, (axL, axR) = plt.subplots(1, 2, figsize=(9.5, 4.2))
    # 左：资产 = 负债 + 权益（堆叠）
    x = [0, 1]
    axL.bar(x, [liab_p, liab_c], 0.5, label="负债", color="#d99694")
    axL.bar(x, [eq_p, eq_c], 0.5, bottom=[liab_p, liab_c], label="所有者权益", color=C_PRIMARY)
    axL.set_xticks(x)
    axL.set_xticklabels(["2024", "2025"])
    axL.set_ylabel("金额（亿元）")
    for xi, (l, e) in zip(x, [(liab_p, eq_p), (liab_c, eq_c)]):
        axL.annotate(f"资产{l+e:.0f}", (xi, l + e), ha="center", va="bottom", fontsize=8, fontweight="bold")
        axL.annotate(f"负债率{l/(l+e)*100:.0f}%", (xi, l / 2), ha="center", fontsize=8, color="white")
    axL.set_title("资产 = 负债 + 所有者权益", fontweight="bold")
    axL.legend(fontsize=8, loc="upper left")

    # 右：负债拆有息 vs 无息
    noninterest_c = liab_c - interest_c
    axR.bar(["负债结构"], [interest_c], 0.4, label=f"有息借款 {interest_c:.0f}", color=C_ACCENT)
    axR.bar(["负债结构"], [noninterest_c], 0.4, bottom=[interest_c], label=f"经营性/无息 {noninterest_c:.0f}", color=C_GRAY)
    axR.set_ylabel("金额（亿元）")
    axR.annotate(f"有息负债/权益\n仅 {interest_c/eq_c*100:.0f}%", (0, interest_c / 2),
                 ha="center", fontsize=9, color="white", fontweight="bold")
    axR.set_title("负债结构：有息 vs 经营性负债", fontweight="bold")
    axR.legend(fontsize=8, loc="upper right")
    lev = liab_c / (liab_c + eq_c) * 100
    ir = interest_c / eq_c * 100
    _save(fig, "balance_structure", "资产负债结构",
          f"资产负债率 {lev:.0f}%；有息借款/股东权益约 {ir:.0f}%，其余为经营性负债。", manifest)


def chart_ocf_vs_ni(fin, manifest):
    ni_c = val(fin, "净利润") / YI
    ni_p = val(fin, "净利润", "prior") / YI
    ocf_c = val(fin, "经营现金流") / YI
    ocf_p = val(fin, "经营现金流", "prior") / YI
    x = [0, 1]
    w = 0.34
    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    b1 = ax.bar([i - w / 2 for i in x], [ni_p, ni_c], w, label="净利润", color=["#f4b9b9", C_ACCENT])
    b2 = ax.bar([i + w / 2 for i in x], [ocf_p, ocf_c], w, label="经营现金流", color=[C_PRIOR, C_CUR])
    _bar_labels(ax, list(b1) + list(b2), "{:.0f}")
    ax.set_xticks(x)
    ax.set_xticklabels(["2024", "2025"])
    ax.set_ylabel("金额（亿元）")
    for xi, (ni, ocf) in zip(x, [(ni_p, ocf_p), (ni_c, ocf_c)]):
        ax.annotate(f"现金含量 {ocf/ni:.2f}×", (xi, ocf), ha="center", va="bottom",
                    fontsize=9, color=C_GREEN, fontweight="bold", xytext=(0, 14), textcoords="offset points")
    ax.set_title("经营现金流 vs 净利润", fontweight="bold")
    ax.legend(fontsize=8)
    ocf_yoy = (ocf_c - ocf_p) / ocf_p * 100
    _save(fig, "ocf_vs_ni", "经营现金流与净利润",
          f"本期经营现金流为净利润 {ocf_c/ni_c:.2f} 倍；经营现金流同比 {ocf_yoy:+.0f}%。", manifest)


def render_all() -> list:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    chosen = setup_chinese_font()
    fin, finds = _load()
    manifest: list = []
    chart_revenue_profit(fin, manifest)
    chart_ocf_bridge(fin, finds, manifest)
    chart_inventory_structure(finds, manifest)
    chart_growth_compare(fin, manifest)
    chart_balance_structure(fin, manifest)
    chart_ocf_vs_ni(fin, manifest)
    (FIG_DIR / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return [chosen, manifest]
