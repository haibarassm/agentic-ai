"""飞书认证：tenant_access_token。

合并自：
- financial-automation: ``get_tenant_access_token(settings)``
- CRM-Assistant: ``get_feishu_tenant_access_token(app_id, app_secret)``

两者打的是同一个端点 ``/open-apis/auth/v3/tenant_access_token/internal``。
"""

from __future__ import annotations

from . import http
from .errors import FeishuAuthError

TENANT_TOKEN_PATH = "/open-apis/auth/v3/tenant_access_token/internal"


def fetch_tenant_access_token(
    *,
    endpoint: str | None,
    app_id: str,
    app_secret: str,
    transport=http,
) -> str:
    if not app_id or not app_secret:
        raise FeishuAuthError("Missing FEISHU_APP_ID or FEISHU_APP_SECRET.")

    response = transport.post_json(
        f"{http.normalize_endpoint(endpoint)}{TENANT_TOKEN_PATH}",
        {"app_id": app_id, "app_secret": app_secret},
    )
    token = str(response.get("tenant_access_token") or "")
    if not token:
        raise FeishuAuthError("Failed to obtain tenant_access_token from Feishu.")
    return token
