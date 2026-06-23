"""跨公司科目别名解析：不同年报对同一科目命名不一（如『五、净利润』vs『四、净利润』、
『所有者权益合计』vs『股东权益合计』、『其中：营业收入』vs『一、营业收入』）。

viz / report 层统一通过 subj() 按规范名取科目，避免把任一公司的科目名写死。
另提供 findings_path()：按股票代码定位每家公司的人工研判文件，使多家公司并存不覆盖。
"""

from __future__ import annotations

from pathlib import Path


def findings_path(stock_code, root):
    """按股票代码定位研判文件：优先 analysis/findings_<代码>.json，
    回退到 analysis/findings.json（单公司便捷场景）。返回 Path（可能不存在，调用方自检）。"""
    root = Path(root)
    if stock_code:
        per = root / "analysis" / f"findings_{stock_code}.json"
        if per.exists():
            return per
    return root / "analysis" / "findings.json"

# 规范名 → 候选子串（按优先级；命中第一个包含该子串的科目）
_ALIASES = {
    # 利润表
    "营业收入": ["其中：营业收入", "一、营业收入"],
    "营业成本": ["其中：营业成本", "减：营业成本"],
    "营业利润": ["三、营业利润", "二、营业利润"],
    "利润总额": ["四、利润总额", "三、利润总额"],
    "净利润": ["五、净利润", "四、净利润"],
    "归母净利润": ["归属于母公司股东的净利润", "归属于母公司所有者的净利润"],
    "研发费用": ["研发费用"],
    "财务费用": ["财务费用"],
    # 资产负债表
    "货币资金": ["货币资金"],
    "应收账款": ["应收账款"],
    "应收款项融资": ["应收款项融资"],
    "存货": ["存货"],
    "固定资产": ["固定资产"],
    "在建工程": ["在建工程"],
    "资产总计": ["资产总计"],
    "流动资产合计": ["流动资产合计"],
    "短期借款": ["短期借款"],
    "长期借款": ["长期借款"],
    "合同负债": ["合同负债"],
    "负债合计": ["负债合计"],
    "所有者权益合计": ["所有者权益合计", "股东权益合计"],
    # 现金流量表
    "销售收现": ["销售商品、提供劳务收到的现金"],
    "经营现金流": ["经营活动产生的现金流量净额"],
    "投资现金流": ["投资活动产生的现金流量净额"],
    "筹资现金流": ["筹资活动产生的现金流量净额"],
    "资本开支": ["购建固定资产"],
    "期末现金": ["期末现金及现金等价物余额", "现金及现金等价物的年末余额"],
}

# 规范名 → 它所在的报表
_STMT_OF = {
    "营业收入": "income", "营业成本": "income", "营业利润": "income", "利润总额": "income",
    "净利润": "income", "归母净利润": "income", "研发费用": "income", "财务费用": "income",
    "货币资金": "balance_sheet", "应收账款": "balance_sheet", "应收款项融资": "balance_sheet",
    "存货": "balance_sheet", "固定资产": "balance_sheet", "在建工程": "balance_sheet",
    "资产总计": "balance_sheet", "流动资产合计": "balance_sheet", "短期借款": "balance_sheet",
    "长期借款": "balance_sheet", "合同负债": "balance_sheet", "负债合计": "balance_sheet",
    "所有者权益合计": "balance_sheet",
    "销售收现": "cash_flow", "经营现金流": "cash_flow", "投资现金流": "cash_flow",
    "筹资现金流": "cash_flow", "资本开支": "cash_flow", "期末现金": "cash_flow",
}


def subj(fin: dict, canonical: str):
    """按规范名取科目 dict {current, prior}；找不到返回 None。"""
    stmt = _STMT_OF.get(canonical)
    if stmt is None:
        return None
    table = fin["statements"][stmt]
    for cand in _ALIASES.get(canonical, [canonical]):
        for k, v in table.items():
            if cand in k:
                return v
    return None


def val(fin: dict, canonical: str, period: str = "current"):
    it = subj(fin, canonical)
    return it[period] if it else None
