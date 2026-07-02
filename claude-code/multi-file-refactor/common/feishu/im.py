"""飞书 IM（即时消息）能力。

这是为 xhs-auto-publisher 新增的通路：原来 xhs 只把二维码图片交给龙虾代发飞书群，
现在可以直接用 FeishuClient 自己把图片发到指定会话。

- 上传图片：``POST /open-apis/im/v1/images``（image_type=message）→ image_key
- 发消息：``POST /open-apis/im/v1/messages?receive_id_type=...``

发图片消息要求应用是目标群里的机器人，且具备 ``im:message:send_as_bot`` 权限。
"""

from __future__ import annotations

import json
import mimetypes
from pathlib import Path
from typing import Any

from . import http
from .errors import FeishuError

IM_IMAGE_PATH = "/open-apis/im/v1/images"
IM_MESSAGE_PATH = "/open-apis/im/v1/messages"

_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"} if token else {}


def upload_im_image(
    *,
    endpoint: str | None,
    token: str,
    image_path: str | Path,
    transport=http,
) -> str:
    """上传一张图片用于 IM 消息，返回 image_key。"""
    path = Path(image_path)
    if not path.exists():
        raise FeishuError(f"QR image file does not exist: {path}")
    if path.suffix.lower() not in _IMAGE_SUFFIXES:
        raise FeishuError(
            f"Feishu IM only accepts jpg/jpeg/png/webp/bmp/gif, got: {path.name}"
        )

    content_type = mimetypes.guess_type(path.name)[0] or "image/png"
    response = transport.post_multipart(
        f"{http.normalize_endpoint(endpoint)}{IM_IMAGE_PATH}",
        fields={"image_type": "message"},
        file_field_name="image",
        file_name=path.name,
        file_bytes=path.read_bytes(),
        content_type=content_type,
        headers=_auth_headers(token),
    )
    data = response.get("data") or {}
    image_key = str(data.get("image_key") or "")
    if not image_key:
        raise FeishuError(f"Feishu IM did not return image_key for {path.name}.")
    return image_key


def send_message(
    *,
    endpoint: str | None,
    token: str,
    receive_id: str,
    msg_type: str,
    content: dict[str, Any],
    receive_id_type: str = "chat_id",
    transport=http,
) -> dict[str, Any]:
    """发送一条 IM 消息（content 会被序列化成 JSON 字符串，符合飞书要求）。"""
    if not receive_id:
        raise FeishuError("Missing Feishu receive_id (e.g. chat_id).")
    return transport.post_json(
        http.build_url(
            f"{http.normalize_endpoint(endpoint)}{IM_MESSAGE_PATH}",
            {"receive_id_type": receive_id_type},
        ),
        {
            "receive_id": receive_id,
            "msg_type": msg_type,
            "content": json.dumps(content, ensure_ascii=False),
        },
        headers=_auth_headers(token),
    )


def send_image_message(
    *,
    endpoint: str | None,
    token: str,
    receive_id: str,
    image_key: str,
    receive_id_type: str = "chat_id",
    transport=http,
) -> dict[str, Any]:
    return send_message(
        endpoint=endpoint,
        token=token,
        receive_id=receive_id,
        msg_type="image",
        content={"image_key": image_key},
        receive_id_type=receive_id_type,
        transport=transport,
    )


def send_text_message(
    *,
    endpoint: str | None,
    token: str,
    receive_id: str,
    text: str,
    receive_id_type: str = "chat_id",
    transport=http,
) -> dict[str, Any]:
    return send_message(
        endpoint=endpoint,
        token=token,
        receive_id=receive_id,
        msg_type="text",
        content={"text": text},
        receive_id_type=receive_id_type,
        transport=transport,
    )
