"""ai_quant —— 从年报 PDF 到 HTML 投研报告的本地分析系统。

分层（DAG）：
    L1 parsing  解析 PDF → data/parsed/financials.json   （代码·确定性）
    L2 viz      结构化数据 → build/figures/*.png          （代码·确定性）
    L4 研判      结构化数据 → analysis/findings.json        （由 Claude Code 亲自产出，非脚本）
    L3 report   数据+图+研判 → reports/*.html              （代码·确定性）
    L5 pipeline 一键编排：L1 →（L2 ∥ L4）→ L3

铁律：代码层只做确定性工作，不在任何脚本里调用大模型 API。
"""
