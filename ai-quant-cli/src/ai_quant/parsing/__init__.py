"""L1 解析层：从年报 PDF 定位合并三表，抽期末/期初数，落盘结构化数据。

产出契约：data/parsed/financials.json
    meta / statements{balance_sheet,income,cash_flow} / checks{balance_identity}
只做解析，不做分析。
"""
