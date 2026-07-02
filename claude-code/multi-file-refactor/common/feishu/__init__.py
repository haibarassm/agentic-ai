"""共享飞书客户端包（common.feishu）。

 Lesson 17 抽取的共享层，供 financial-automation、CRM-Assistant、xhs-auto-publisher 复用。

分层：
- ``errors``：统一异常树（FeishuError → Auth / HTTP / API）
- ``http``：传输层（post_json / post_multipart / request_json，统一超时与错误）
- ``auth``：tenant_access_token
- ``bitable``：多维表格 OpenAPI（list / batch_create / batch_update / 媒体上传）
- ``im``：即时消息（上传图片 / 发图片 / 发文本）——为 xhs 新增
- ``client``：FeishuClient 门面
"""

from __future__ import annotations

from .client import FeishuClient
from .errors import FeishuAPIError, FeishuAuthError, FeishuError, FeishuHTTPError

__all__ = [
    "FeishuClient",
    "FeishuError",
    "FeishuAuthError",
    "FeishuHTTPError",
    "FeishuAPIError",
]
