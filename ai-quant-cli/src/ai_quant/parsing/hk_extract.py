"""港版（H 股 IFRS）年报/季报解析器。

适用：小米等港交所披露的中文（繁体）财报，pdfplumber 能干净提取文本的 PDF。
（字体编码损坏、pdfplumber 出 cid 乱码的 PDF 不在本模块处理范围 —— 那种走 OCR。）

与 A 股 CAS 的差异（本模块负责适配）：
- 科目是繁体 IFRS 命名：收入/銷售成本/經營利潤/期間利潤/資產總額/權益總額… → 归一到 A 股 canonical 名。
- 负数用括号 (77,331,498) —— parse_number 已支持。
- 行内夹「附註号」（如「收入 2 99,141,618」里的 2）—— 取行末两个数字值为 current/prior。
- 借款分流動/非流動两行同名「借款」—— 按 BS 段落（流動負債/非流動負債）拆成 短期/长期借款。
- 期间：从表头「截至YYYY年M月…」判定 → 年报 'YYYY' / 季报 'YYYYQ1' 等（带粒度后缀）。

输出 schema 与 A 股 extract_financials 一致，下游 L2/L3/L5 无需改动。
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pdfplumber

from ..common import canonical_item, parse_number

# 繁体 IFRS 科目 → A 股 canonical 规范名（能让现有 charts/report 直接用）。
# key 用去空白后的繁体原文；value 是输出 statements 里的 key。
_HK_ALIASES: dict[str, str] = {
    # 損益表
    "收入": "营业收入",
    "銷售成本": "营业成本",
    "毛利": "毛利",
    "研發開支": "研发费用",
    "銷售及推廣開支": "销售费用",
    "行政開支": "管理费用",
    "經營利潤": "营业利润",
    "除所得稅前利潤": "利润总额",
    "除所得税前利潤": "利润总额",
    "所得稅費用": "所得税费用",
    "期間利潤": "净利润",
    "年度利潤": "净利润",
    "本公司擁有人": "归属于母公司所有者的净利润",  # 「下列人士應佔：— 本公司擁有人」
    "非控股權益": "少数股东损益",  # 損益表里是少数股东损益（BS 里同行名 but 语义是权益，按表区分）
    # 資產負債表 —— 資產
    "資產總額": "资产总计",
    "存貨": "存货",
    "現金及現金等價物": "货币资金",
    "貿易應收款項及應收票據": "应收账款",
    "貿易應收款項": "应收账款",
    "物業、廠房及設備": "固定资产",
    "物業、廠房及設": "固定资产",  # 容错（表格折行/OCR 残缺）
    # 資產負債表 —— 權益及負債
    "權益總額": "所有者权益合计",
    "負債總額": "负债合计",
    "流動負債": "__section_current_liab__",
    "非流動負債": "__section_noncurrent_liab__",
    "借款": "__borrowings__",  # 按所在段落拆 短期/长期
    "貿易應付款項": "应付账款",
    # 現金流量表
    "經營活動": "__cf_operating__",  # 子串匹配，下面特殊处理
    "投資活動": "__cf_investing__",
    "融資活動": "__cf_financing__",
}

# 现金流净额行的繁体关键词 → canonical（用子串包含判定，因命名带「（所用）╱所得」等变体）。
_CF_NET_MAP = [
    ("經營", "经营活动产生的现金流量净额"),
    ("投資", "投资活动产生的现金流量净额"),
    ("融資", "筹资活动产生的现金流量净额"),
]

_VALUE_TOKEN = re.compile(r"^[\d,()．.\-—]+$")


def _split_label_values(line: str) -> tuple[str, list[float | None]] | None:
    """把一行拆成 (label, [values...])。

    - 先去掉行首 bullet（—、　、-、全半角空格）。
    - label = 行首连续的「含 CJK 字符」token。
    - values = 行末的数值 token（取最后两个，对应 current/prior 两列）。
    - 附註号（如「2」「2, 3」）夹在 label 与 values 之间，因不是最后两个，自动排除。
    """
    s = line.strip().lstrip("—－-　 \t").strip()
    if not s:
        return None
    tokens = s.split()
    # label：连续含 CJK 的前缀 token
    label_tokens: list[str] = []
    for tok in tokens:
        if re.search(r"[一-龥]", tok):
            label_tokens.append(tok)
        else:
            break
    if not label_tokens:
        return None
    label = "".join(label_tokens)
    rest = tokens[len(label_tokens):]
    num_tokens = [t for t in rest if _VALUE_TOKEN.match(t)]
    if len(num_tokens) < 2:
        return None  # 非两列数据行（表头/小节标题/单值）
    current = parse_number(num_tokens[-2])
    prior = parse_number(num_tokens[-1])
    return label, [current, prior]


def _page_text(pdf, idx: int) -> str:
    return pdf.pages[idx].extract_text() or ""


def _find_page(pdf, anchor: str, limit: int = 60) -> int | None:
    for idx in range(0, min(limit, len(pdf.pages))):
        if anchor in _page_text(pdf, idx):
            return idx
    return None


def _detect_hk_period(text_block: str) -> str:
    """从表头判定 period：'截至2026年3月31日止三個月' → '2026Q1'；'於2025年12月31日'/'2025年度' → '2025'。"""
    m = re.search(r"(20\d{2})\s*年\s*(\d{1,2})\s*月", text_block)
    if m:
        year, month = m.group(1), int(m.group(2))
        gran = {3: "Q1", 6: "H1", 9: "Q3"}.get(month, "")
        return f"{year}{gran}"  # month=12 → gran="" → 年报
    m = re.search(r"(20\d{2})\s*年度", text_block)
    return m.group(1) if m else ""


def _parse_statement(pdf, start_idx: int, stop_anchors: list[str], max_pages: int = 4) -> dict[str, dict]:
    """从 start_idx 解析一张表，遇到 stop_anchors 或超出 max_pages 停。

    返回 {canonical_item: {"current":v,"prior":v}}。
    BS 的借款按段落（流動/非流動負債）拆 短期/长期。
    """
    out: dict[str, dict] = {}
    section: str = ""  # BS 段落：current_liab / noncurrent_liab / ""
    for offset in range(max_pages):
        idx = start_idx + offset
        if idx >= len(pdf.pages):
            break
        text = _page_text(pdf, idx)
        if offset > 0:
            for a in stop_anchors:
                if a in text:
                    return out
        for line in text.splitlines():
            if any(a in line for a in stop_anchors) and offset > 0:
                return out
            parsed = _split_label_values(line)
            if not parsed:
                # 段落标题跟踪（流動負債/非流動負債）
                stripped = line.strip()
                if "流動負債" in stripped and "非" not in stripped:
                    section = "current_liab"
                elif "非流動負債" in stripped:
                    section = "noncurrent_liab"
                continue
            label, vals = parsed
            current, prior = vals[0], vals[1]

            # 现金流净额行（子串匹配，含「（所用）╱所得」变体）
            handled = False
            for kw, canon in _CF_NET_MAP:
                if kw in label and ("淨額" in label or "净額" in label):
                    out[canon] = {"current": current, "prior": prior}
                    handled = True
                    break
            if handled:
                continue

            canon = _HK_ALIASES.get(label)
            if canon is None:
                continue
            if canon == "__borrowings__":
                # 按段落拆
                if section == "current_liab":
                    out.setdefault("短期借款", {"current": None, "prior": None})
                    out["短期借款"] = {"current": current, "prior": prior}
                elif section == "noncurrent_liab":
                    out.setdefault("长期借款", {"current": None, "prior": None})
                    out["长期借款"] = {"current": current, "prior": prior}
                continue
            if canon.startswith("__"):
                continue  # 段落标记
            out[canon] = {"current": current, "prior": prior}
    return out


def extract_hk_financials(pdf_path: str | Path, *, stock_code: str | None = None) -> dict[str, Any]:
    """解析港版中文财报 PDF → financials dict（schema 与 A 股一致）。"""
    pdf = pdfplumber.open(str(pdf_path))
    path = Path(pdf_path)

    # 用完整「中期簡明合併…」标题定位主报表（避开 MD&A 里的引用式提及）
    inc_idx = _find_page(pdf, "中期簡明合併損益表") or _find_page(pdf, "簡明合併損益表")
    bs_idx = _find_page(pdf, "中期簡明合併資產負債表") or _find_page(pdf, "簡明合併資產負債表")
    cf_idx = _find_page(pdf, "中期簡明合併現金流量表") or _find_page(pdf, "簡明合併現金流量表")

    # 每张表只在自己「之外」的锚点停止 —— 同表续页（…（續））不触发停止。
    # 注意：不能用「附註」做停止词 —— 报表页本身就有「附註」列和脚注引用，会误判进入附注章。
    inc_stops = ["合併資產負債表", "合併現金流量表", "合併綜合收益表", "合併權益變動表"]
    bs_stops = ["合併損益表", "合併現金流量表", "合併綜合收益表", "合併權益變動表"]
    cf_stops = ["合併損益表", "合併資產負債表", "合併綜合收益表", "合併權益變動表"]

    income = _parse_statement(pdf, inc_idx, inc_stops) if inc_idx is not None else {}
    balance_sheet = _parse_statement(pdf, bs_idx, bs_stops, max_pages=3) if bs_idx is not None else {}
    cash_flow = _parse_statement(pdf, cf_idx, cf_stops) if cf_idx is not None else {}

    # 派生：归母权益 = 权益总额 - 少数股东权益(BS)
    eq = balance_sheet.get("所有者权益合计", {}).get("current")
    # BS 里的「非控股權益」会被 _HK_ALIASES 映射成「少数股东损益」——这里按 BS 语义修正
    if "少数股东损益" in balance_sheet:
        balance_sheet["少数股东权益"] = balance_sheet.pop("少数股东损益")
    minor = balance_sheet.get("少数股东权益", {}).get("current")
    if eq is not None and minor is not None and "归属于母公司所有者权益合计" not in balance_sheet:
        balance_sheet["归属于母公司所有者权益合计"] = {
            "current": eq - minor,
            "prior": (balance_sheet["所有者权益合计"].get("prior") or 0) - (balance_sheet.get("少数股东权益", {}).get("prior") or 0),
        }

    # period 从損益表表头判定
    period_text = _page_text(pdf, inc_idx) if inc_idx is not None else ""
    period = _detect_hk_period(period_text)

    # 恒等式自检
    checks = _identity_check(balance_sheet)

    meta = {
        "company": _detect_company(pdf, stock_code),
        "stock_code": stock_code or "",
        "period": period,
        "currency": "CNY",
        "unit": "千元",
        "source_pdf": path.name,
        "parsed_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "format": "HK-IFRS",
        "statement_pages": {
            "income": [inc_idx + 1] if inc_idx is not None else [],
            "balance_sheet": [bs_idx + 1] if bs_idx is not None else [],
            "cash_flow": [cf_idx + 1] if cf_idx is not None else [],
        },
    }
    return {
        "meta": meta,
        "statements": {"balance_sheet": balance_sheet, "income": income, "cash_flow": cash_flow},
        "summary_history": {"periods": [], "series": {}, "unit": "千元"},  # 季报无多年汇总；年报另填
        "checks": checks,
    }


def _detect_company(pdf, stock_code: str | None) -> str:
    for idx in range(0, min(8, len(pdf.pages))):
        for line in _page_text(pdf, idx).splitlines():
            if "小米" in line or "集團" in line:
                name = re.sub(r"\s+", "", line.strip())
                if 2 <= len(name) <= 30:
                    return name
    return ""


def _identity_check(balance_sheet: dict) -> dict:
    """资产总计 == 负债合计 + 所有者权益合计（容差 1e-4）。"""
    def _chk(curr_key: str) -> dict:
        a = balance_sheet.get("资产总计", {}).get(curr_key)
        l = balance_sheet.get("负债合计", {}).get(curr_key)
        e = balance_sheet.get("所有者权益合计", {}).get(curr_key)
        if a is None or l is None or e is None:
            return {"ok": False, "diff": None}
        rhs = l + e
        return {"ok": abs(a - rhs) <= 1e-4, "lhs": a, "rhs": rhs,
                "liabilities": l, "equity": e, "diff": a - rhs, "tolerance": 1e-4}

    return {"balance_identity": {
        "current": _chk("current"),
        "prior": _chk("prior"),
    }}
