"""ai_quant —— 本地量化投研系统包。

分层（DAG）：
- parsing: L1 PDF → financials.json（合并三表 + 多年汇总 + 恒等式自检）
- viz:     L2 financials.json → 图表 PNG + manifest
- report:  L3 fan-in 汇编 HTML
- pipeline: L5 一键编排（含 L4 研判闸门）

铁律：研判由 Claude Code 亲自做（产出 analysis/findings_*.json），代码不调大模型 API。
"""
