"""飞书多维表格（Bitable）OpenAPI。

合并自：
- financial-automation: ``batch_create_records`` / ``upload_attachment``（无分页读取）
- CRM-Assistant: ``list_feishu_bitable_tables / fields / records``、
  ``batch_create_feishu_bitable_records``、``batch_update_feishu_bitable_records``

分页默认值沿用 CRM：tables 100/页，fields/records 500/页。
batch_create 按 batch_size 分块（FA 行为，飞书单次上限 500）。
"""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any

from . import http
from .errors import FeishuError

_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"} if token else {}


def _base(endpoint: str | None, *parts: str) -> str:
    return "/".join([http.normalize_endpoint(endpoint), *parts])


def _paginate(
    *,
    url: str,
    token: str,
    page_size: int,
    transport,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    page_token: str | None = None
    while True:
        response = transport.request_json(
            url,
            method="GET",
            headers=_auth_headers(token),
            query={"page_size": page_size, "page_token": page_token},
        )
        data = response.get("data") or {}
        items.extend(list(data.get("items") or []))
        if not data.get("has_more"):
            break
        page_token = data.get("page_token")
        if not page_token:
            break
    return items


def list_tables(*, endpoint: str | None, token: str, app_token: str, transport=http) -> list[dict[str, Any]]:
    return _paginate(
        url=_base(endpoint, "open-apis", "bitable", "v1", "apps", app_token, "tables"),
        token=token,
        page_size=100,
        transport=transport,
    )


def list_fields(
    *,
    endpoint: str | None,
    token: str,
    app_token: str,
    table_id: str,
    transport=http,
) -> list[dict[str, Any]]:
    return _paginate(
        url=_base(endpoint, "open-apis", "bitable", "v1", "apps", app_token, "tables", table_id, "fields"),
        token=token,
        page_size=500,
        transport=transport,
    )


def list_records(
    *,
    endpoint: str | None,
    token: str,
    app_token: str,
    table_id: str,
    transport=http,
) -> list[dict[str, Any]]:
    return _paginate(
        url=_base(endpoint, "open-apis", "bitable", "v1", "apps", app_token, "tables", table_id, "records"),
        token=token,
        page_size=500,
        transport=transport,
    )


def _chunk(records: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    return [records[index : index + size] for index in range(0, len(records), size)]


def batch_create_records(
    *,
    endpoint: str | None,
    token: str,
    app_token: str,
    table_id: str,
    records: list[dict[str, Any]],
    batch_size: int = 500,
    transport=http,
    return_raw: bool = False,
) -> int | dict[str, Any]:
    """批量新建记录。

    - ``return_raw=False``（默认，financial-automation 用）：返回写入条数 int。
    - ``return_raw=True``（CRM-Assistant 用）：返回最后一次响应的原始 dict，供报告留痕。
    """
    if not table_id:
        raise FeishuError("Missing Bitable table_id.")
    total_written = 0
    last_response: dict[str, Any] = {}
    for chunk in _chunk(records, max(1, min(batch_size, 500))):
        last_response = transport.post_json(
            _base(
                endpoint,
                "open-apis",
                "bitable",
                "v1",
                "apps",
                app_token,
                "tables",
                table_id,
                "records",
                "batch_create",
            ),
            {"records": chunk},
            headers=_auth_headers(token),
        )
        data = last_response.get("data", {})
        items = data.get("records", []) if isinstance(data, dict) else []
        total_written += len(items) if items else len(chunk)
    return last_response if return_raw else total_written


def batch_update_records(
    *,
    endpoint: str | None,
    token: str,
    app_token: str,
    table_id: str,
    records: list[dict[str, Any]],
    batch_size: int = 500,
    transport=http,
    return_raw: bool = False,
) -> int | dict[str, Any]:
    if not table_id:
        raise FeishuError("Missing Bitable table_id.")
    total_written = 0
    last_response: dict[str, Any] = {}
    for chunk in _chunk(records, max(1, min(batch_size, 500))):
        last_response = transport.post_json(
            _base(
                endpoint,
                "open-apis",
                "bitable",
                "v1",
                "apps",
                app_token,
                "tables",
                table_id,
                "records",
                "batch_update",
            ),
            {"records": chunk},
            headers=_auth_headers(token),
        )
        total_written += len(chunk)
    return last_response if return_raw else total_written


def upload_drive_media(
    *,
    endpoint: str | None,
    token: str,
    app_token: str,
    file_path: str | Path,
    transport=http,
) -> dict[str, Any]:
    """上传到飞书云文档（/drive/v1/medias/upload_all），返回 file_token 等信息。

    financial-automation 用它把票据附件挂到 Bitable 附件字段。
    """
    path = Path(file_path)
    if not path.exists():
        raise FeishuError(f"Attachment file does not exist: {path}")

    mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    parent_type = "bitable_image" if path.suffix.lower() in _IMAGE_SUFFIXES else "bitable_file"
    response = transport.post_multipart(
        _base(endpoint, "open-apis", "drive", "v1", "medias", "upload_all"),
        fields={
            "file_name": path.name,
            "parent_type": parent_type,
            "parent_node": app_token,
            "size": str(path.stat().st_size),
        },
        file_field_name="file",
        file_name=path.name,
        file_bytes=path.read_bytes(),
        content_type=mime_type,
        headers=_auth_headers(token),
    )
    data = response.get("data", {})
    file_token = str(data.get("file_token") or "")
    if not file_token:
        raise FeishuError(f"Feishu did not return file_token for {path.name}.")
    return {
        "file_token": file_token,
        "name": path.name,
        "type": mime_type,
        "size": path.stat().st_size,
    }
