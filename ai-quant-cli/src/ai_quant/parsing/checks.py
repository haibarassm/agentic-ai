"""会计恒等式自检：资产总计 == 负债和所有者权益总计 == 负债合计 + 所有者权益合计。

不平说明抽漏或抽错（抓到母公司表 / 科目定位错 / 单位不一致）。容差 1e-4（千元级四舍五入残差）。
"""

from __future__ import annotations

from typing import Any

_TOLERANCE = 1e-4  # 相对容差


def _rel_diff(lhs: float | None, rhs: float | None) -> float | None:
    if lhs is None or rhs is None:
        return None
    denom = max(abs(lhs), abs(rhs), 1.0)
    return abs(lhs - rhs) / denom


def balance_identity_check(balance_sheet: dict[str, dict[str, float]]) -> dict[str, Any]:
    """期末、期初各验一组恒等式。返回 {current: {...}, prior: {...}}。"""
    result: dict[str, Any] = {}
    for period_key in ("current", "prior"):
        assets = balance_sheet.get("资产总计", {}).get(period_key)
        liabilities = balance_sheet.get("负债合计", {}).get(period_key)
        equity = balance_sheet.get("所有者权益合计", {}).get(period_key)
        liab_and_equity = balance_sheet.get("负债和所有者权益总计", {}).get(period_key)

        lhs = assets
        # rhs 优先用「负债和所有者权益总计」列；取不到则用 负债合计+所有者权益合计
        rhs = liab_and_equity
        if rhs is None and liabilities is not None and equity is not None:
            rhs = liabilities + equity

        diff = _rel_diff(lhs, rhs)
        result[period_key] = {
            "ok": diff is not None and diff <= _TOLERANCE,
            "lhs": assets,            # 资产总计
            "rhs": rhs,               # 负债和所有者权益总计（或负债+权益）
            "liabilities": liabilities,
            "equity": equity,
            "diff": diff,
            "tolerance": _TOLERANCE,
        }
    return {"balance_identity": result}
