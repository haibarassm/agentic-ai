"""统一异常树。

所有飞书客户端错误都继承 ``RuntimeError``，这样三处历史调用点的捕获仍然有效：

- financial-automation: ``except BitableSyncError``（在 sync_bitable 里把
  ``BitableSyncError`` 设为 ``FeishuError`` 的别名）
- CRM-Assistant: ``except RuntimeError``（FeishuError 本身就是 RuntimeError）
- xhs-auto-publisher: 新代码直接用 FeishuError
"""

from __future__ import annotations


class FeishuError(RuntimeError):
    """所有飞书客户端错误的基类。"""


class FeishuAuthError(FeishuError):
    """获取 tenant_access_token 失败（缺凭证 / 飞书拒绝发 token）。"""


class FeishuHTTPError(FeishuError):
    """传输层失败：网络不可达、非 2xx HTTP 状态码等。"""


class FeishuAPIError(FeishuError):
    """飞书 OpenAPI 返回了非 0 业务码（code != 0）。"""

    def __init__(self, message: str, *, code: int | None = None, payload: dict | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.payload = payload
