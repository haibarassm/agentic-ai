"""L1 解析层：从年报 PDF 定位合并三表，抽期末/期初数，落盘结构化数据。

定位策略（阶段 2 实测得出）：
- 财报正文里三表带编号小节标题：``1、合并资产负债表`` / ``3、合并利润表`` /
  ``5、合并现金流量表``（母公司是 2/4/6）。用这些编号锚点切片，比按页码切可靠
  ——因为一页里可能同时出现上一张表的尾巴和下一张表的开头。
- 单位为「千元」（年报原文如此），数值按原文存为 float，meta.unit 标明。
- 每行形如 ``科目名 期末数 期初数``；按行解析、只接受“同一行既有名又有数”的条目，
  避免被跨行折行的子科目污染（关键科目与各合计行都在单行内）。
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

import pdfplumber

# 三表编号小节标题锚点：1/3/5 = 合并，2/4/6 = 母公司
_SECTION_RE = re.compile(r"^\s*(\d+)\s*、\s*(合并|母公司)\s*(资产负债表|利润表|现金流量表)")

# 跨页运行页眉 / 编制说明 / 单位 / 日期 等噪声行
_NOISE_RE = re.compile(
    r"(年年度报告全文|^编制单位|^单位：|^财务附注|^二、财务报表|^\d{4}年12月31日"
    r"|后附财务报表附注|^资产 附注|^附注七)"
)

# 数字 token：可带千分位、可负、可被中/英文括号包裹表示负数
_NUM_TOKEN_RE = re.compile(r"^[（(]?[-－—]?[\d,]+(?:\.\d+)?[)）]?$")

# 合并三表分别需要的「当前列」表头语义（仅用于 meta 记录，不影响解析）
_PERIOD_LABELS = {
    "balance_sheet": ("期末余额", "期初余额"),
    "income": ("本期", "上期"),
    "cash_flow": ("本期", "上期"),
}


def parse_num(token: str):
    """把一个数字 token 解析成 float；括号代表负数；无效返回 None。"""
    t = token.strip().replace(",", "")
    neg = False
    if (t.startswith("(") and t.endswith(")")) or (t.startswith("（") and t.endswith("）")):
        neg = True
        t = t[1:-1]
    t = t.replace("－", "-").replace("—", "-")
    if t in ("", "-"):
        return None
    try:
        v = float(t)
    except ValueError:
        return None
    return -v if neg else v


def _normalize_parens(line: str) -> str:
    """规整括号内紧贴的空格：``(649,350 )`` → ``(649,350)``，让负数 token 可被识别。"""
    line = re.sub(r"([(（])\s+", r"\1", line)
    line = re.sub(r"\s+([)）])", r"\1", line)
    return line


def split_name_and_numbers(line: str):
    """把一行拆成 (科目名, [数值...])；只取行尾连续的数字 token。

    返回的数值列表保留出现顺序。注意：部分年报（如比亚迪）在科目名与金额之间
    多一列『附注编号』，因此行尾可能出现 3 个数字 [附注号, 期末, 期初]——取值时
    由 _pick_periods 取最后两个，自动丢掉附注号。
    若行尾没有数字 token，数值列表为空。
    """
    tokens = _normalize_parens(line).split()
    nums = []
    while tokens and _NUM_TOKEN_RE.match(tokens[-1]) and any(c.isdigit() for c in tokens[-1]):
        nums.insert(0, tokens.pop())
    name = "".join(tokens).strip()  # 中文科目名内部无空格，直接拼回
    values = [parse_num(t) for t in nums]
    return name, values


def _pick_periods(values):
    """从行尾数字列表取 (期末/本期, 期初/上期)：标准 PRC 报表只有两列数值，
    取最后两个即可（前面多出来的是附注编号列）。"""
    vals = [v for v in values if v is not None]
    if len(vals) >= 2:
        return vals[-2], vals[-1]
    if len(vals) == 1:
        return vals[-1], None
    return None, None


def _collect_lines(pdf, page_start: int, page_end: int):
    """收集 [page_start, page_end] 页（1-based，含端点）的所有非噪声文本行。"""
    lines = []
    for pno in range(page_start, page_end + 1):
        text = pdf.pages[pno - 1].extract_text() or ""
        for raw in text.splitlines():
            s = raw.strip()
            if not s or _NOISE_RE.search(s):
                continue
            lines.append(s)
    return lines


def _find_sections(lines):
    """返回所有报表小节标题的位置：[{idx, num, kind(合并/母公司), type(资产负债表/利润表/现金流量表)}]。

    不依赖编号顺序——各家年报里『合并』与『母公司』的小节编号顺序并不一致。
    """
    secs = []
    for i, s in enumerate(lines):
        m = _SECTION_RE.match(s)
        if m:
            secs.append({"idx": i, "num": int(m.group(1)), "kind": m.group(2), "type": m.group(3)})
    return secs


def _slice_consolidated(lines, secs, stype):
    """切出某张『合并』报表的行：从它的标题切到下一张报表标题为止。"""
    for j, sec in enumerate(secs):
        if sec["kind"] == "合并" and sec["type"] == stype:
            start = sec["idx"]
            end = secs[j + 1]["idx"] if j + 1 < len(secs) else len(lines)
            return lines[start:end]
    return []


def _is_category_header(line: str) -> bool:
    """形如 “流动资产：” 的分类小标题（无数值，不应并入下一个科目名）。"""
    return line.endswith("：") or line.endswith(":")


def _parse_statement(section_lines, statement_key):
    """把一个小节的行解析成 {科目名: {current, prior}}。

    单行 ``科目名 期末数 期初数`` 直接成条目。另用一个小状态机回收「夹心折行」：
        '四、利润总额（亏损总额以“－”号填'   ← 名字上半（无数）
        '89,526,545 63,182,039'              ← 纯数字行
        '列）'                                ← 名字下半（无数）
    把上下半拼成完整名、中间数字行作其值。无值科目（结算备付金等）自然被丢弃。
    """
    items = {}
    pending_name = ""   # 已累积、尚无数值的名字片段
    held_values = None  # 已出现、但名字还没拼全的数值

    def commit_pending():
        nonlocal pending_name, held_values
        name = pending_name.strip()
        if held_values is not None and name and name not in items:
            cur, pri = _pick_periods(held_values)
            items[name] = {"current": cur, "prior": pri}
        pending_name = ""
        held_values = None

    for s in section_lines:
        if _SECTION_RE.match(s):
            continue  # 跳过小节标题行本身
        name, values = split_name_and_numbers(s)

        if name and values:
            # 完整单行科目：先结清可能挂起的夹心项，再登记自己
            commit_pending()
            current, prior = _pick_periods(values)
            if name not in items:
                items[name] = {"current": current, "prior": prior}
        elif values and not name:
            # 纯数字行：属于正在拼接的夹心科目
            held_values = values
        elif name and not values:
            # 纯名字行：分类小标题则重置，否则作为名字片段累积
            if _is_category_header(s):
                commit_pending()
            else:
                pending_name += name
        # 空行已在 _collect_lines 过滤

    commit_pending()
    return items


_UNIT_RE = re.compile(r"单位[:：]\s*(千元|万元|元)")
_COMPANY_RE = re.compile(r"编制单位[:：]\s*([一-龥A-Za-z（）()]+(?:公司|集团|股份))")
_PERIOD_RE = re.compile(r"(\d{4})\s*年年度报告")


def _detect_meta(pdf, page_start, lines, pdf_path, stock_code):
    """从 PDF 文本动态识别公司名/单位/报告期，不写死任何公司。"""
    head_text = "\n".join(lines[:60])
    first_text = pdf.pages[0].extract_text() or ""

    unit_m = _UNIT_RE.search("\n".join(lines[:30]))
    unit = unit_m.group(1) if unit_m else "千元"

    company = None
    comp_m = _COMPANY_RE.search(head_text)
    if comp_m:
        company = comp_m.group(1)
    if not company:
        for ln in first_text.splitlines():
            s = ln.strip()
            if s.endswith("公司") and 4 <= len(s) <= 20:
                company = s
                break

    period_m = _PERIOD_RE.search(first_text)
    period = f"{period_m.group(1)}FY" if period_m else "FY"

    code = stock_code
    if not code:
        cover = "\n".join((pdf.pages[i].extract_text() or "") for i in range(min(3, len(pdf.pages))))
        cm = re.search(r"(?:股票|证券)代码[:：\s]*([0-9]{6})", cover)
        if cm:
            code = cm.group(1)
    return {"company": company or "（未识别）", "unit": unit, "period": period, "stock_code": code}


def extract_financials(pdf_path: str, stock_code: str = "") -> dict:
    """主入口：解析年报 PDF，返回符合数据契约的结构化 dict。

    公司名 / 单位 / 报告期从 PDF 文本动态识别；stock_code 可选传入。
    """
    with pdfplumber.open(pdf_path) as pdf:
        # 三张合并报表都落在「二、财务报表」区，先粗定位含关键字的页范围再精切。
        kw_pages = []
        for i, page in enumerate(pdf.pages):
            t = page.extract_text() or ""
            if "合并资产负债表" in t or "合并现金流量表" in t:
                kw_pages.append(i + 1)
        page_start = min(kw_pages)
        page_end = min(max(kw_pages) + 3, len(pdf.pages))  # 现金流量表后留几页冗余
        lines = _collect_lines(pdf, page_start, page_end)
        secs = _find_sections(lines)

        statements = {
            "balance_sheet": _parse_statement(_slice_consolidated(lines, secs, "资产负债表"), "balance_sheet"),
            "income": _parse_statement(_slice_consolidated(lines, secs, "利润表"), "income"),
            "cash_flow": _parse_statement(_slice_consolidated(lines, secs, "现金流量表"), "cash_flow"),
        }

        detected = _detect_meta(pdf, page_start, lines, pdf_path, stock_code)
        meta = {
            "company": detected["company"],
            "stock_code": detected.get("stock_code") or stock_code,
            "period": detected["period"],
            "currency": "CNY",
            "unit": detected["unit"],
            "source_pdf": pdf_path,
            "parsed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "period_labels": _PERIOD_LABELS,
            "consolidated_pages": {"scan_from": page_start, "scan_to": page_end},
        }

    from .checks import balance_identity_check

    checks = {"balance_identity": balance_identity_check(statements["balance_sheet"])}
    return {"meta": meta, "statements": statements, "checks": checks}
