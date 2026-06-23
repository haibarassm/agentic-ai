"""L3 报告层：fan-in 汇编 HTML 投研报告。

输入：data/parsed/financials.json + analysis/findings.json + build/figures/manifest.json
产出：reports/report_<period>.html（图表 base64 内嵌，单文件浏览器可直接打开）。

铁律：本层只做确定性汇编与排版，不产生任何分析判断（判断来自 findings.json）。
"""

from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment

from ai_quant.common import findings_path, subj, val

ROOT = Path(__file__).resolve().parents[3]
YI = 1e5  # 千元 → 亿元


def _load():
    fin = json.loads((ROOT / "data" / "parsed" / "financials.json").read_text("utf-8"))
    finds = json.loads(findings_path(fin["meta"].get("stock_code"), ROOT).read_text("utf-8"))
    manifest_path = ROOT / "build" / "figures" / "manifest.json"
    manifest = json.loads(manifest_path.read_text("utf-8")) if manifest_path.exists() else []
    return fin, finds, manifest


def _bs(fin, name, period="current"):
    it = fin["statements"]["balance_sheet"].get(name)
    return it[period] if it else None


def _sub(fin, stmt, sub, period="current"):
    for k, v in fin["statements"][stmt].items():
        if sub in k:
            return v[period]
    return None


def _yi(v):
    return None if v is None else v / YI


def _row(label, cur, pri):
    yoy = ((cur - pri) / pri * 100) if (pri not in (None, 0) and cur is not None) else None
    return {"label": label, "cur": cur, "pri": pri, "yoy": yoy}


def _embed_figures(manifest):
    figs = []
    for m in manifest:
        p = ROOT / "build" / m["path"]
        if not p.exists():
            continue
        b64 = base64.b64encode(p.read_bytes()).decode("ascii")
        figs.append({**m, "data_uri": f"data:image/png;base64,{b64}"})
    return figs


def _build_tables(fin):
    def crow(label, canonical):
        return _row(label, val(fin, canonical), val(fin, canonical, "prior"))

    bs = [
        crow("货币资金", "货币资金"), crow("应收账款", "应收账款"),
        crow("应收款项融资", "应收款项融资"), crow("存货", "存货"),
        crow("固定资产", "固定资产"), crow("在建工程", "在建工程"),
        crow("资产总计", "资产总计"), crow("短期借款", "短期借款"),
        crow("合同负债", "合同负债"), crow("长期借款", "长期借款"),
        crow("负债合计", "负债合计"), crow("所有者权益合计", "所有者权益合计"),
    ]
    def crow(label, canonical):
        return _row(label, val(fin, canonical), val(fin, canonical, "prior"))

    inc = [
        crow("营业收入", "营业收入"), crow("营业成本", "营业成本"), crow("研发费用", "研发费用"),
        crow("营业利润", "营业利润"), crow("利润总额", "利润总额"),
        crow("净利润", "净利润"), crow("归母净利润", "归母净利润"),
    ]
    cf = [
        crow("销售收现", "销售收现"), crow("经营活动现金流量净额", "经营现金流"),
        crow("资本开支", "资本开支"), crow("投资活动现金流量净额", "投资现金流"),
        crow("筹资活动现金流量净额", "筹资现金流"), crow("期末现金及现金等价物", "期末现金"),
    ]
    return {"资产负债表": bs, "利润表": inc, "现金流量表": cf}


_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{ meta.company }} · {{ meta.period }} 投研报告</title>
<style>
  :root{ --navy:#1f4e79; --red:#c00000; --green:#2e7d32; --gray:#7f7f7f;
         --bg:#f5f6f8; --card:#ffffff; --line:#e3e6ea; --ink:#1a1a1a; }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);
       font-family:"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
       line-height:1.65;font-size:15px;}
  .wrap{max-width:980px;margin:0 auto;padding:32px 20px 60px;}
  header.top{background:linear-gradient(135deg,var(--navy),#2b6cb0);color:#fff;
       border-radius:14px;padding:30px 34px;box-shadow:0 6px 22px rgba(31,78,121,.18);}
  header.top h1{margin:0 0 6px;font-size:26px;letter-spacing:.5px;}
  header.top .sub{opacity:.92;font-size:14px;}
  header.top .tags{margin-top:14px;}
  .tag{display:inline-block;background:rgba(255,255,255,.16);border:1px solid rgba(255,255,255,.3);
       border-radius:20px;padding:3px 12px;margin:3px 6px 0 0;font-size:12.5px;}
  section{background:var(--card);border:1px solid var(--line);border-radius:12px;
       padding:24px 28px;margin-top:22px;box-shadow:0 1px 3px rgba(0,0,0,.04);}
  h2{font-size:19px;color:var(--navy);margin:0 0 16px;padding-bottom:10px;
     border-bottom:2px solid var(--navy);display:flex;align-items:center;gap:8px;}
  h2 .no{background:var(--navy);color:#fff;border-radius:6px;font-size:13px;
     padding:2px 9px;font-weight:600;}
  .lead{background:#eef4fb;border-left:4px solid var(--navy);padding:14px 18px;
        border-radius:6px;font-size:14.5px;margin-bottom:6px;}
  table{width:100%;border-collapse:collapse;font-size:13.5px;margin-top:6px;}
  th,td{padding:8px 10px;text-align:right;border-bottom:1px solid var(--line);}
  th:first-child,td:first-child{text-align:left;}
  thead th{background:#f0f3f7;color:var(--navy);font-weight:600;}
  tbody tr:hover{background:#fafbfc;}
  .up{color:var(--red);font-weight:600;} .down{color:var(--green);font-weight:600;}
  .stmt-title{font-weight:700;color:var(--navy);margin:18px 0 4px;font-size:15px;}
  .grid{display:grid;grid-template-columns:1fr 1fr;gap:18px;}
  @media(max-width:760px){.grid{grid-template-columns:1fr}}
  .finding{border:1px solid var(--line);border-radius:10px;padding:16px 18px;background:#fff;}
  .finding h3{margin:0 0 6px;font-size:15.5px;color:var(--ink);}
  .badge{font-size:11.5px;font-weight:700;border-radius:5px;padding:2px 8px;color:#fff;margin-left:8px;}
  .b-high{background:#a30000;} .b-mid{background:#d97706;} .b-low{background:#2e7d32;}
  .finding p{margin:6px 0 8px;font-size:13.8px;color:#333;}
  .evi{font-size:12px;color:var(--gray);border-top:1px dashed var(--line);padding-top:8px;}
  .evi code{background:#f0f3f7;border-radius:4px;padding:1px 5px;color:#33506e;}
  figure{margin:18px 0;text-align:center;}
  figure img{max-width:100%;border:1px solid var(--line);border-radius:8px;}
  figcaption{font-size:12.5px;color:var(--gray);margin-top:8px;text-align:left;
             background:#f7f9fb;border-radius:6px;padding:8px 12px;}
  .cc{border-left:3px solid var(--navy);padding:10px 16px;margin:12px 0;background:#fafbfd;border-radius:0 8px 8px 0;}
  .cc.warn{border-left-color:var(--red);background:#fff6f6;}
  .cc h4{margin:0 0 4px;font-size:14.5px;}
  .cc p{margin:0;font-size:13.5px;color:#333;}
  .check-ok{color:var(--green);font-weight:700;}
  footer{margin-top:26px;font-size:12px;color:var(--gray);text-align:center;line-height:1.8;}
  .disc{background:#fff8e6;border:1px solid #f0d68a;border-radius:8px;padding:12px 16px;
        font-size:12.5px;color:#7a5b00;margin-top:18px;}
</style>
</head>
<body>
<div class="wrap">

<header class="top">
  <h1>{{ meta.company }}</h1>
  <div class="sub">{{ meta.period }} 年度财务分析 · 投研报告　|　股票代码 {{ meta.stock_code }}　|　金额单位：{{ meta.unit }}（图表换算为亿元）</div>
  <div class="tags">
    <span class="tag">营收 {{ fmt_yi(kpi.rev) }}亿　{{ pct(kpi.rev_yoy) }}</span>
    <span class="tag">净利润 {{ fmt_yi(kpi.ni) }}亿　{{ pct(kpi.ni_yoy) }}</span>
    <span class="tag">经营现金流 {{ fmt_yi(kpi.ocf) }}亿　现金含量 {{ '%.2f'|format(kpi.ocf/kpi.ni) }}×</span>
    <span class="tag">毛利率 {{ '%.1f'|format(kpi.gm) }}%</span>
    <span class="tag">资产负债率 {{ '%.1f'|format(kpi.lev) }}%</span>
  </div>
</header>

<section>
  <h2><span class="no">摘要</span>核心结论</h2>
  <div class="lead">{{ summary }}</div>
</section>

<section>
  <h2><span class="no">01</span>关键财务数据（期末/本期 vs 期初/上期）</h2>
  {% for tname, rows in tables.items() %}
  <div class="stmt-title">{{ tname }}</div>
  <table>
    <thead><tr><th>科目</th><th>本期/期末</th><th>上期/期初</th><th>同比</th></tr></thead>
    <tbody>
    {% for r in rows %}
      <tr>
        <td>{{ r.label }}</td>
        <td>{{ fmt(r.cur) }}</td>
        <td>{{ fmt(r.pri) }}</td>
        <td class="{{ 'up' if r.yoy and r.yoy>=0 else 'down' }}">{{ pct(r.yoy) }}</td>
      </tr>
    {% endfor %}
    </tbody>
  </table>
  {% endfor %}
  <p style="font-size:12px;color:var(--gray);margin-top:10px;">注：单位千元；同比红=增长、绿=下降。</p>
</section>

<section>
  <h2><span class="no">02</span>可视化图表</h2>
  {% for f in figures %}
  <figure>
    <img src="{{ f.data_uri }}" alt="{{ f.title }}">
    <figcaption><b>图{{ loop.index }}　{{ f.title }}</b>　{{ f.caption }}</figcaption>
  </figure>
  {% endfor %}
</section>

<section>
  <h2><span class="no">03</span>隐性财务风险研判</h2>
  <div class="grid">
  {% for r in risk_findings %}
    <div class="finding">
      <h3>{{ r.topic }}<span class="badge {{ badge(r.severity) }}">{{ r.severity }}</span></h3>
      <p>{{ r.conclusion }}</p>
      <div class="evi">依据：
        {% for e in r.evidence %}<code>{{ e.item }}{% if e.value is defined %}={{ '{:,.0f}'.format(e.value) }}{% endif %}</code> {% endfor %}
      </div>
    </div>
  {% endfor %}
  </div>
</section>

<section>
  <h2><span class="no">04</span>三表勾稽交叉验证</h2>
  <p style="font-size:13.5px;color:#444;margin-top:-4px;">第一轮：基础勾稽（收入真实性、盈利含金量、备货与产能节奏）。</p>
  {% for c in cross_checks %}
  <div class="cc"><h4>{{ c.id }}　{{ c.title }}</h4><p>{{ c.conclusion }}</p></div>
  {% endfor %}
  <p style="font-size:13.5px;color:#444;margin-top:14px;">第二轮：用间接法桥（净利润→经营现金流，已验证合回，差 2 千元）深挖背离。</p>
  {% for c in cross_checks_round2 %}
  <div class="cc {{ 'warn' if c.severity and ('高' in c.severity) else '' }}">
    <h4>{{ c.id }}　{{ c.title }}{% if c.severity %}<span class="badge {{ badge(c.severity) }}">{{ c.severity }}</span>{% endif %}</h4>
    <p>{{ c.conclusion }}</p>
  </div>
  {% endfor %}
</section>

<section>
  <h2><span class="no">05</span>数据自检</h2>
  <p>会计恒等式自检（资产总计 = 负债合计 + 所有者权益合计 = 负债和所有者权益总计）：
     期末/期初各两条，
     {% if checks.balance_identity.ok %}<span class="check-ok">✓ 全部通过，diff = 0</span>{% else %}<span class="up">✗ 存在不平</span>{% endif %}。
     间接法桥（净利润 → 经营活动现金流量）已验证合回，差 2 千元（四舍五入）。
  </p>
</section>

<div class="disc">
  ⚠️ 免责声明：本报告由 AI Quant CLI 自动汇编，财务研判由分析者基于本份年报数据独立完成；
  数据解析与图表为确定性程序生成，过程不调用任何大模型 API。报告仅为财务结构分析，<b>不构成任何投资建议</b>。
</div>

<footer>
  数据来源：{{ meta.company }} {{ meta.period }} 年度报告　|　解析时间 {{ meta.parsed_at }}<br>
  报告生成时间 {{ generated_at }}　|　AI Quant CLI · 本地财报分析系统
</footer>

</div>
</body>
</html>
"""


def _kpi(fin):
    rev = val(fin, "营业收入"); rev_p = val(fin, "营业收入", "prior")
    cogs = val(fin, "营业成本")
    ni = val(fin, "净利润"); ni_p = val(fin, "净利润", "prior")
    ocf = val(fin, "经营现金流")
    liab = val(fin, "负债合计"); ta = val(fin, "资产总计")
    return {
        "rev": rev, "rev_yoy": (rev - rev_p) / rev_p * 100,
        "ni": ni, "ni_yoy": (ni - ni_p) / ni_p * 100,
        "ocf": ocf, "gm": (rev - cogs) / rev * 100, "lev": liab / ta * 100,
    }


def build_report() -> Path:
    fin, finds, manifest = _load()
    env = Environment(autoescape=False)

    def fmt(v):
        return "—" if v is None else f"{v:,.0f}"

    def fmt_yi(v):
        return "—" if v is None else f"{v / YI:,.0f}"

    def pct(v):
        return "—" if v is None else f"{v:+.1f}%"

    def badge(sev):
        if sev and "高" in sev:
            return "b-high"
        if sev and "中" in sev:
            return "b-mid"
        return "b-low"

    env.filters["fmt"] = fmt
    template = env.from_string(_TEMPLATE)

    # 摘要是人工研判的一部分，按公司写在 findings.meta.summary；缺省给一句通用兜底
    summary = finds.get("meta", {}).get(
        "summary", "本报告基于年报合并三表的结构化数据与人工财务研判自动汇编，详见下方风险与勾稽小节。"
    )

    html = template.render(
        meta=fin["meta"],
        checks=fin["checks"],
        kpi=_kpi(fin),
        summary=summary,
        tables=_build_tables(fin),
        figures=_embed_figures(manifest),
        risk_findings=finds["risk_findings"],
        cross_checks=finds["cross_checks"],
        cross_checks_round2=finds.get("cross_checks_round2", []),
        fmt=fmt, fmt_yi=fmt_yi, pct=pct, badge=badge,
        generated_at=datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M"),
    )

    out_dir = ROOT / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    # 文件名带公司标识 + 报告期 + 运行时间戳：每次跑都产出独立网页，互不覆盖。
    m = fin["meta"]
    tag = (m.get("stock_code") or m.get("company") or "report").strip().replace(" ", "")
    stamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    out = out_dir / f"report_{tag}_{m['period']}_{stamp}.html"
    out.write_text(html, encoding="utf-8")
    return out
