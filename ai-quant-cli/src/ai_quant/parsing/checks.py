"""会计恒等式自检（资产 = 负债 + 所有者权益）。

校验两条，期末/期初各算一次：
  (a) 资产总计 == 负债和所有者权益总计   （报表内勾稽）
  (b) 资产总计 == 负债合计 + 所有者权益合计
因千元四舍五入会有微小残差，用相对容差判断，而非严格相等。
"""

from __future__ import annotations

# 相对容差：|diff| / max(|lhs|,1) <= 此值即视为通过。千元级残差远小于此。
_REL_TOL = 1e-6


# 不同年报对同一总计科目的命名差异（所有者权益 / 股东权益）
_ALIASES = {
    "资产总计": ["资产总计"],
    "负债和所有者权益总计": ["负债和所有者权益总计", "负债和股东权益总计"],
    "负债合计": ["负债合计"],
    "所有者权益合计": ["所有者权益合计", "股东权益合计"],
}


def _get(bs: dict, name: str, period: str):
    for cand in _ALIASES.get(name, [name]):
        item = bs.get(cand)
        if item and item.get(period) is not None:
            return item[period]
    return None


def _check_one(lhs, rhs):
    if lhs is None or rhs is None:
        return {"ok": False, "lhs": lhs, "rhs": rhs, "diff": None, "reason": "缺科目"}
    diff = lhs - rhs
    ok = abs(diff) <= _REL_TOL * max(abs(lhs), 1.0)
    return {"ok": ok, "lhs": lhs, "rhs": rhs, "diff": diff}


def balance_identity_check(balance_sheet: dict) -> dict:
    """对资产负债表做两条恒等式自检，期末/期初各一组。"""
    result = {}
    for period in ("current", "prior"):
        assets = _get(balance_sheet, "资产总计", period)
        le_total = _get(balance_sheet, "负债和所有者权益总计", period)
        liab = _get(balance_sheet, "负债合计", period)
        equity = _get(balance_sheet, "所有者权益合计", period)

        a_eq_le = _check_one(assets, le_total)
        a_eq_liab_plus_eq = _check_one(
            assets, (liab + equity) if (liab is not None and equity is not None) else None
        )
        result[period] = {
            "资产总计=负债和所有者权益总计": a_eq_le,
            "资产总计=负债合计+所有者权益合计": a_eq_liab_plus_eq,
            "ok": a_eq_le["ok"] and a_eq_liab_plus_eq["ok"],
        }
    result["ok"] = result["current"]["ok"] and result["prior"]["ok"]
    return result
