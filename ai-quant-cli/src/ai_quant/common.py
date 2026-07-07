"""共享工具：数字清洗、科目别名归一、单位换算。

年报数字格式坑：千分位逗号、括号负数 (1,234)、空单元格、单位（元/千元/万元）。
科目命名坑：『所有者权益合计』vs『股东权益合计』、『净利润』vs『四、净利润』。
"""

from __future__ import annotations

import re
from typing import Any

# 千元 → 亿（出图更易读）。1 亿 = 1e8 元 = 1e5 千元。
K_TO_YI = 1e5

# 科目别名归一表：把不同公司/不同报表里的异名映射到规范名。
# key=异名（小写、去空白/标点后的形式），value=规范名。
_ITEM_ALIASES: dict[str, str] = {
    # 所有者权益
    "所有者权益合计": "所有者权益合计",
    "股东权益合计": "所有者权益合计",
    "归属于母公司所有者权益合计": "归属于母公司所有者权益合计",
    "归属于母公司所有者权益": "归属于母公司所有者权益合计",
    "归属于上市公司股东的净资产": "归属于母公司所有者权益合计",
    # 净利润
    "净利润": "净利润",
    "四、净利润": "净利润",
    "五、净利润": "净利润",
    "归属于母公司所有者的净利润": "归属于母公司所有者的净利润",
    "归属于上市公司股东的净利润": "归属于母公司所有者的净利润",
    "归属于母公司股东净利润": "归属于母公司所有者的净利润",
    "归属于母公司股东的净利润": "归属于母公司所有者的净利润",
    "归属于母公司所有者净利润": "归属于母公司所有者的净利润",
    # 营收
    "营业收入": "营业收入",
    "一、营业总收入": "营业收入",
    "一、营业收入": "营业收入",
    "营业总收入": "营业收入",
    # 资产/负债合计
    "资产总计": "资产总计",
    "资产总额": "资产总计",
    "负债合计": "负债合计",
    "负债和所有者权益总计": "负债和所有者权益总计",
    "负债和所有者权益": "负债和所有者权益总计",
    "负债及所有者权益总计": "负债和所有者权益总计",
    "负债和股东权益总计": "负债和所有者权益总计",
    "归属于母公司所有者权益合计": "归属于母公司所有者权益合计",
    "归属于母公司股东权益合计": "归属于母公司所有者权益合计",
    "归属于上市公司股东的净资产": "归属于母公司所有者权益合计",
    # 经营现金流
    "经营活动产生的现金流量净额": "经营活动产生的现金流量净额",
    "经营活动产生的现金流量": "经营活动产生的现金流量净额",
    "经营活动现金流量净额": "经营活动产生的现金流量净额",
}


def _norm_key(name: str) -> str:
    """科目名归一为字典 key：去空白、去前导序号/前缀、去尾部括注。"""
    s = (name or "").strip()
    # 去前导编号：『四、』『1、』『（1）』『1.』
    s = re.sub(r"^[一-龥]{1,2}、", "", s)
    s = re.sub(r"^\d+[、.．]", "", s)
    s = re.sub(r"^[（(]\d+[)）]", "", s)
    # 去前缀：其中：/ 减：/ 加：
    s = re.sub(r"^(其中|减|加)[:：]", "", s)
    # 去尾部括注（『（亏损以"－"号填列）』『（元/股）』等，非科目身份的一部分）
    s = re.sub(r"[（(][^（）()]*[)）]$", "", s)
    # 去尾部未闭合括注（单元格被截断、缺右括号的情况，如『利润总额（亏损总额以"－"号填』）
    s = re.sub(r"[（(][^（）()]*$", "", s)
    s = s.replace(" ", "").replace("　", "")
    return s


def canonical_item(name: str) -> str:
    """科目名归一到规范名（无别名则返回去空白/去序号的原名）。"""
    key = _norm_key(name)
    return _ITEM_ALIASES.get(key, key)


def parse_number(raw: Any) -> float | None:
    """把年报单元格解析成 float。

    - ``"333,512,927"`` → 333512927.0
    - ``"(1,234)"`` / ``"-1,234"`` → -1234.0（括号=负数）
    - ``""`` / ``None`` → None（空单元格）
    - ``"17.04%"`` → 0.1704（百分比转小数）
    """
    if raw is None:
        return None
    s = str(raw).strip()
    if s == "" or s == "-" or s == "—" or s == "N/A":
        return None
    # 百分比
    if s.endswith("%"):
        try:
            return float(s[:-1]) / 100.0
        except ValueError:
            return None
    negative = s.startswith("(") and s.endswith(")")
    cleaned = s.strip("()").replace(",", "").replace("，", "")
    if cleaned.startswith("-"):
        negative = True
        cleaned = cleaned.lstrip("-")
    if cleaned == "":
        return None
    try:
        value = float(cleaned)
    except ValueError:
        return None
    return -value if negative else value


def looks_numeric(raw: Any) -> bool:
    """单元格是否像一个数字（含千分位/括号负数/百分号）。"""
    return parse_number(raw) is not None


def to_yi(value_kilo_yuan: float | None) -> float | None:
    """千元 → 亿元（出图用）。"""
    if value_kilo_yuan is None:
        return None
    return value_kilo_yuan / K_TO_YI


# 单位 → 换算到「千元」的乘子（1 此单位 = 多少千元）
_UNIT_TO_KILO: dict[str, float] = {
    "元": 0.001,
    "千元": 1.0,
    "万元": 10.0,
    "百万元": 1000.0,
    "亿元": 100_000.0,
}


def unit_scale(from_unit: str, to_unit: str) -> float:
    """从 from_unit 换算到 to_unit 的乘子。用于统一 summary 与 statements 的单位。"""
    f = _UNIT_TO_KILO.get(from_unit, 1.0)
    t = _UNIT_TO_KILO.get(to_unit, 1.0)
    return f / t
