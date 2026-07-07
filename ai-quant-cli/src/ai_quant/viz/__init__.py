"""L2 出图层：读 financials.json 渲染图表 PNG + manifest.json。"""

from .charts import render_all_figures, setup_chinese_font

__all__ = ["render_all_figures", "setup_chinese_font"]
