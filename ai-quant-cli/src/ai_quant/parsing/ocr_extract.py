"""OCR 解析器：处理字体编码损坏、pdfplumber 出 cid 乱码的 PDF（如小米港股年报 AR）。

核心思路（可靠性的关键）：
- 数字字体（DIN）的 Unicode 映射完好 → fitz 能正确提取数字及其坐标。
- 中文标签字体（HYQiHei-GBK-EUC-H）缺 ToUnicode → fitz 提取为乱码，必须 OCR。
- 因此：fitz 取「数字+坐标」，OCR 取「标签+坐标」，按 y 行对齐、按 x 分列。
- 用五年财务概要页（损益+资产负债）一次拿到 5 年序列 + 当年/上年两期。

坐标尺度：fitz 用 PDF 点（72dpi），OCR 用渲染像素（200dpi），需统一（OCR ÷ (200/72)）。
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import fitz
from rapidocr_onnxruntime import RapidOCR

# 标签识别：OCR 出的繁简混杂标签（含误识）→ 规范 canonical 名。
# 策略：先繁→简归一，再用「关键词组合」容错匹配（OCR 常误识擁→摊、權→槿、佔→估）。
# 权益类靠恒等式派生，不依赖 OCR 识别「權益」（OCR 几乎必错）。

# 常见财务用字 繁→简（覆盖本项目遇到的）。
_FAN_TO_JIAN = str.maketrans({
    "資": "资", "產": "产", "總": "总", "額": "额", "權": "权", "負": "负",
    "務": "务", "動": "动", "應": "应", "佔": "占", "擁": "拥", "營": "营",
    "綜": "综", "際": "际", "國": "国", "計": "计", "調": "调", "淨": "净",
    "損": "损", "貨": "货", "業": "业", "經": "经", "報": "报", "灣": "湾",
    "現": "现", "員": "员", "從": "从", "為": "为", "潤": "润", "債": "债",
    "據": "据", "構": "构", "確": "确", "較": "较", "項": "项", "虧": "亏",
    "處": "处", "導": "导", "於": "于", "機": "机", "電": "电", "車": "车",
})


def _norm_simp(t: str) -> str:
    return t.translate(_FAN_TO_JIAN)


def _match_label(text: str) -> str | None:
    """OCR 标签 → canonical（繁→简归一后，关键词组合匹配）。"""
    t = _norm_simp(text)
    # 顺序敏感：更具体的在前
    if "所得税前" in t:
        return "利润总额"
    if "本公司" in t and "利润" in t and "综合" not in t:
        return "归属于母公司所有者的净利润"  # 本公司擁有人應佔利潤（OCR 常把擁/佔识错，但「本公司」「利润」稳）
    if "本公司" in t and "综合" in t:
        return None  # 综合收益行不计入主表
    if "年度综合" in t or "综合收益" in t:
        return None
    if "经营利润" in t:
        return "营业利润"
    if "年度利润" in t or "期间利润" in t:
        return "净利润"
    if "经调整" in t:
        return None  # non-IFRS 调整数不计入
    if "资产总" in t:
        return "资产总计"
    if "负债总" in t:
        return "负债合计"
    if "非流动资" in t:
        return "非流动资产"
    if "流动资" in t:
        return "流动资产"
    if "非流动负" in t:
        return "非流动负债"
    if "流动负" in t:
        return "流动负债"
    if "毛利" in t:
        return "毛利"
    if t.endswith("收入") or t == "收入":
        return "营业收入"
    return None

# 渲染 DPI（越高越准但越慢）
_RENDER_DPI = 200
_SCALE = _RENDER_DPI / 72.0  # PDF点 ↔ 渲染像素

_OCR = None


def _get_ocr() -> RapidOCR:
    global _OCR
    if _OCR is None:
        _OCR = RapidOCR()
    return _OCR


def _fitz_numbers(page) -> list[tuple[float, float, float]]:
    """返回 [(value, x_center, y_center)]（PDF 点），value 已处理括号负数/千分位。"""
    out: list[tuple[float, float, float]] = []
    d = page.get_text("dict")
    for blk in d.get("blocks", []):
        for line in blk.get("lines", []):
            # 同一行的相邻 span 拼接（数字可能被切，但大数通常单 span）
            for sp in line.get("spans", []):
                t = sp["text"].strip()
                if not re.fullmatch(r"\d{1,3}(?:,\d{3})+|\(\d{1,3}(?:,\d{3})+\)|\d+\.\d+|\(\d+\.\d+\)", t):
                    continue
                neg = t.startswith("(") and t.endswith(")")
                cleaned = t.strip("()").replace(",", "")
                try:
                    val = float(cleaned)
                except ValueError:
                    continue
                if neg:
                    val = -val
                x = (sp["bbox"][0] + sp["bbox"][2]) / 2
                y = (sp["bbox"][1] + sp["bbox"][3]) / 2
                out.append((val, x, y))
    return out


def _ocr_blocks(page) -> list[tuple[str, float, float]]:
    """OCR 一页 → [(text, x_center, y_center)]（渲染像素坐标）。"""
    pix = page.get_pixmap(dpi=_RENDER_DPI)
    tmp = Path(__file__).resolve().parents[3] / "build" / f"_ocr_p{page.number+1}.png"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    pix.save(str(tmp))
    res, _ = _get_ocr()(str(tmp))
    out = []
    for item in (res or []):
        box, txt = item[0], item[1]
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        out.append((txt, sum(xs) / 4, sum(ys) / 4))
    return out


def _find_summary_page(doc) -> int | None:
    """找『五年财务概要』页：含 5 个相近年份(20XX年)表头的早期页。用 OCR 探测前 12 页。"""
    ocr = _get_ocr()
    for idx in range(0, min(12, len(doc))):
        pix = doc[idx].get_pixmap(dpi=_RENDER_DPI)
        tmp = Path(__file__).resolve().parents[3] / "build" / f"_scan_p{idx+1}.png"
        pix.save(str(tmp))
        res, _ = ocr(str(tmp))
        years = set()
        for item in (res or []):
            m = re.match(r"^(20\d{2})年$", item[1].strip())
            if m:
                years.add(m.group(1))
        if len(years) >= 4:  # 至少 4 个年头条 → 摘要页
            return idx
    return None


def _extract_summary_table(doc, page_idx: int) -> tuple[dict[str, dict[int, float]], list[str]]:
    """解析一页五年摘要 → ({canonical: {year: value}}, [years排序])。

    坐标统一到 PDF 点：OCR 坐标 ÷ _SCALE。
    """
    page = doc[page_idx]
    nums = _fitz_numbers(page)  # PDF 点
    blocks = _ocr_blocks(page)  # 像素 → 转 PDF 点

    # 年份列：含 '20XX年' 的块，取最上面一组的 5 个，按 x 排序
    year_blocks = []
    for txt, x, y in blocks:
        m = re.match(r"^(20\d{2})年$", txt.strip())
        if m:
            year_blocks.append((m.group(1), x / _SCALE, y / _SCALE))
    if len(year_blocks) < 4:
        return {}, []
    year_blocks.sort(key=lambda t: t[2])  # 按 y
    top_years = year_blocks[:6]
    top_years.sort(key=lambda t: t[1])  # 按 x：列序
    year_cols = [(int(yr), x) for yr, x, _ in top_years]
    years = sorted({yr for yr, _ in year_cols})

    # 标签行：含 CJK、非年份、非单位词
    UNIT_WORDS = ("人民", "千元", "百萬", "百万", "億", "元", "百萬台", "附", "註", "注")
    label_rows: list[tuple[str, float]] = []  # (canonical, y_PDF)
    for txt, x, y in blocks:
        t = txt.strip()
        if not re.search(r"[一-龥]", t):
            continue
        if re.match(r"^20\d{2}年$", t):
            continue
        if any(w in t for w in UNIT_WORDS) and len(t) <= 6:
            continue
        canon = _match_label(t)
        if canon:
            label_rows.append((canon, y / _SCALE))

    # 每个 canonical 取其出现的 y（可能多行同 label，取最上方）
    seen: dict[str, float] = {}
    for canon, y in label_rows:
        if canon not in seen:
            seen[canon] = y

    # 对齐：每个标签 y 附近(±8 PDF点)的数字，按 x 分到最近年份列
    series: dict[str, dict[int, float]] = {}
    for canon, ly in seen.items():
        row_nums = [(v, x, y) for (v, x, y) in nums if abs(y - ly) < 8]
        if not row_nums:
            continue
        per_year: dict[int, float] = {}
        for v, x, _ in row_nums:
            yr = min(year_cols, key=lambda kc: abs(kc[1] - x))[0]
            per_year[yr] = v  # 同列多次以最后一次为准（罕见）
        if per_year:
            series[canon] = per_year
    return series, years


def extract_ocr_financials(pdf_path: str | Path, *, stock_code: str | None = None,
                           summary_page: int | None = None) -> dict[str, Any]:
    """OCR 解析字体损坏的 PDF → financials dict（schema 与 A 股一致）。

    依赖年报内嵌的『五年财务概要』页（损益+资产负债）。现金流若不在摘要页则缺。
    """
    doc = fitz.open(str(pdf_path))
    path = Path(pdf_path)

    page_idx = (summary_page - 1) if summary_page else _find_summary_page(doc)
    if page_idx is None:
        raise RuntimeError("未找到五年财务概要页（前12页无≥4个年头条）")
    series, years = _extract_summary_table(doc, page_idx)

    # 负债合计派生：非流动负债 + 流动负债（『負債總額』标签行常被 OCR 漏检，但两段负债标签能识别）
    ncl = series.get("非流动负债", {})
    cl = series.get("流动负债", {})
    if ncl and cl:
        series["负债合计"] = {y: ncl.get(y, 0) + cl.get(y, 0) for y in ncl if y in cl}

    # 权益靠恒等式派生（OCR 几乎认不出「權益」二字）：所有者权益合计 = 资产总计 - 负债合计
    a_series = series.get("资产总计", {})
    l_series = series.get("负债合计", {})
    if a_series and l_series:
        series["所有者权益合计"] = {y: a_series.get(y, 0) - l_series.get(y, 0) for y in a_series if y in l_series}

    years_sorted = sorted(years)
    latest = max(years_sorted) if years_sorted else 0
    prev = latest - 1

    # summary_history：头部指标的 5 年序列
    summary_series: dict[str, list[float]] = {}
    SUMMARY_KEYS = ["营业收入", "归属于母公司所有者的净利润", "毛利", "营业利润",
                     "资产总计", "所有者权益合计", "负债合计"]
    for key in SUMMARY_KEYS:
        if key in series:
            summary_series[key] = [series[key].get(y) for y in years_sorted]

    # statements：latest vs prev 两期
    def _cp(key: str) -> dict:
        s = series.get(key, {})
        return {"current": s.get(latest), "prior": s.get(prev)}

    income = {
        "营业收入": _cp("营业收入"),
        "毛利": _cp("毛利"),
        "营业利润": _cp("营业利润"),
        "利润总额": _cp("利润总额"),
        "净利润": _cp("净利润"),
        "归属于母公司所有者的净利润": _cp("归属于母公司所有者的净利润"),
    }
    balance_sheet = {
        "资产总计": _cp("资产总计"),
        "负债合计": _cp("负债合计"),
        "所有者权益合计": _cp("所有者权益合计"),
        "流动资产": _cp("流动资产"),
        "非流动资产": _cp("非流动资产"),
    }

    meta = {
        "company": "小米集团",
        "stock_code": stock_code or "01810",
        "period": str(latest),
        "currency": "CNY",
        "unit": "千元",
        "source_pdf": path.name,
        "parsed_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "format": "HK-IFRS-OCR",
        "summary_page": page_idx + 1,
        "note": "字体编码损坏，数字来自 fitz、标签来自 OCR 坐标对齐；现金流未在五年摘要页则缺。",
    }
    return {
        "meta": meta,
        "statements": {"balance_sheet": balance_sheet, "income": income, "cash_flow": {}},
        "summary_history": {"periods": [str(y) for y in years_sorted], "series": summary_series, "unit": "千元"},
        "checks": _identity_check(balance_sheet),
    }


def _identity_check(balance_sheet: dict) -> dict:
    def _chk(key: str) -> dict:
        a = balance_sheet.get("资产总计", {}).get(key)
        l = balance_sheet.get("负债合计", {}).get(key)
        e = balance_sheet.get("所有者权益合计", {}).get(key)
        if a is None or l is None or e is None:
            return {"ok": False, "diff": None}
        rhs = l + e
        return {"ok": abs(a - rhs) <= max(1.0, abs(a) * 1e-4), "lhs": a, "rhs": rhs,
                "liabilities": l, "equity": e, "diff": a - rhs, "tolerance": 1e-4}

    return {"balance_identity": {"current": _chk("current"), "prior": _chk("prior")}}
