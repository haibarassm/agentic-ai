"""FeishuClient —— 三个 app 共用的飞书门面。

把 auth / bitable / im 三层收口成一个客户端，供 financial-automation、
CRM-Assistant、xhs-auto-publisher 复用。tenant_access_token 懒加载并在进程内缓存
（同一次 CLI 批处理内复用，避免重复换取）。

测试时可通过 ``transport=`` 注入假传输层，避免真实网络。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import auth, bitable, http, im
from .errors import FeishuError


class FeishuClient:
    def __init__(
        self,
        *,
        app_id: str = "",
        app_secret: str = "",
        endpoint: str | None = None,
        transport=http,
    ) -> None:
        self.app_id = app_id
        self.app_secret = app_secret
        self.endpoint = http.normalize_endpoint(endpoint)
        self._transport = transport
        self._token: str | None = None

    # ---- 认证 -----------------------------------------------------------
    def get_tenant_access_token(self) -> str:
        if self._token is None:
            self._token = auth.fetch_tenant_access_token(
                endpoint=self.endpoint,
                app_id=self.app_id,
                app_secret=self.app_secret,
                transport=self._transport,
            )
        return self._token

    def _token_or(self, access_token: str | None) -> str:
        return access_token if access_token is not None else self.get_tenant_access_token()

    # ---- Bitable --------------------------------------------------------
    def list_tables(self, app_token: str, *, access_token: str | None = None) -> list[dict[str, Any]]:
        return bitable.list_tables(
            endpoint=self.endpoint, token=self._token_or(access_token), app_token=app_token, transport=self._transport
        )

    def list_fields(
        self, app_token: str, table_id: str, *, access_token: str | None = None
    ) -> list[dict[str, Any]]:
        return bitable.list_fields(
            endpoint=self.endpoint,
            token=self._token_or(access_token),
            app_token=app_token,
            table_id=table_id,
            transport=self._transport,
        )

    def list_records(
        self, app_token: str, table_id: str, *, access_token: str | None = None
    ) -> list[dict[str, Any]]:
        return bitable.list_records(
            endpoint=self.endpoint,
            token=self._token_or(access_token),
            app_token=app_token,
            table_id=table_id,
            transport=self._transport,
        )

    def batch_create_records(
        self,
        app_token: str,
        table_id: str,
        records: list[dict[str, Any]],
        *,
        batch_size: int = 500,
        access_token: str | None = None,
    ) -> int:
        return bitable.batch_create_records(
            endpoint=self.endpoint,
            token=self._token_or(access_token),
            app_token=app_token,
            table_id=table_id,
            records=records,
            batch_size=batch_size,
            transport=self._transport,
        )

    def batch_update_records(
        self,
        app_token: str,
        table_id: str,
        records: list[dict[str, Any]],
        *,
        batch_size: int = 500,
        access_token: str | None = None,
    ) -> int:
        return bitable.batch_update_records(
            endpoint=self.endpoint,
            token=self._token_or(access_token),
            app_token=app_token,
            table_id=table_id,
            records=records,
            batch_size=batch_size,
            transport=self._transport,
        )

    def upload_drive_media(
        self, app_token: str, file_path: str | Path, *, access_token: str | None = None
    ) -> dict[str, Any]:
        return bitable.upload_drive_media(
            endpoint=self.endpoint,
            token=self._token_or(access_token),
            app_token=app_token,
            file_path=file_path,
            transport=self._transport,
        )

    # ---- IM（xhs 用）----------------------------------------------------
    def upload_im_image(self, image_path: str | Path, *, access_token: str | None = None) -> str:
        return im.upload_im_image(
            endpoint=self.endpoint,
            token=self._token_or(access_token),
            image_path=image_path,
            transport=self._transport,
        )

    def send_image_message(
        self, receive_id: str, image_key: str, *, receive_id_type: str = "chat_id", access_token: str | None = None
    ) -> dict[str, Any]:
        return im.send_image_message(
            endpoint=self.endpoint,
            token=self._token_or(access_token),
            receive_id=receive_id,
            image_key=image_key,
            receive_id_type=receive_id_type,
            transport=self._transport,
        )

    def send_text_message(
        self, receive_id: str, text: str, *, receive_id_type: str = "chat_id", access_token: str | None = None
    ) -> dict[str, Any]:
        return im.send_text_message(
            endpoint=self.endpoint,
            token=self._token_or(access_token),
            receive_id=receive_id,
            text=text,
            receive_id_type=receive_id_type,
            transport=self._transport,
        )


__all__ = ["FeishuClient", "FeishuError"]
