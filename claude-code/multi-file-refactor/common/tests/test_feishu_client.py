"""common.feishu 共享客户端的单元测试。

用 FakeTransport 模拟真实 http 契约（业务码 code != 0 时抛 FeishuAPIError），
全程不发真实网络请求。CI 把它作为「common 包测试」运行。
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

# 让 tests 直接 import common.feishu（common 包就在父目录）
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from common.feishu import (  # noqa: E402
    FeishuAPIError,
    FeishuAuthError,
    FeishuClient,
    FeishuError,
    FeishuHTTPError,
)
from common.feishu import http  # noqa: E402


class FakeTransport:
    """模拟 common.feishu.http 的契约：code != 0 抛 FeishuAPIError。

    默认响应：code=0 + 自动 tenant_access_token（避免 token 测试失败）。
    可通过 routes 覆写特定端点的响应。
    """

    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.routes: dict[str, dict] = {}
        self._default_response: dict = {"code": 0, "tenant_access_token": "default-tok"}
        # 状态机：按同一 URL 调用次数返回不同响应（支持分页测试）
        self._call_counter: dict[str, int] = {}

    def _respond(self, url: str) -> dict:
        self._call_counter[url] = self._call_counter.get(url, 0) + 1
        call_num = self._call_counter[url]
        for pattern, response in self.routes.items():
            if pattern in url:
                # 如果是列表，按调用次数选；否则直接返回
                if isinstance(response, list):
                    if call_num <= len(response):
                        resp = response[call_num - 1]
                    else:
                        resp = response[-1]
                else:
                    resp = response
                code = int(resp.get("code", 0) or 0)
                if code != 0:
                    raise FeishuAPIError(
                        f"Feishu API returned code {code}: {resp.get('msg')}",
                        code=code,
                        payload=resp,
                    )
                return resp
        return self._default_response

    def post_json(self, url, payload, *, headers=None, timeout=60):  # noqa: ANN001
        self.calls.append(("post_json", url, payload, headers))
        return self._respond(url)

    def request_json(self, url, *, method="GET", headers=None, body=None, query=None, timeout=60):  # noqa: ANN001
        self.calls.append(("request_json", url, method, query, headers))
        return self._respond(url)

    def post_multipart(self, url, *, fields, file_field_name, file_name, file_bytes, content_type, headers=None, timeout=60):  # noqa: ANN001
        self.calls.append(("post_multipart", url, fields, file_field_name))
        return self._respond(url)


def _png(path: Path) -> Path:
    path.write_bytes(b"\x89PNG\r\n\x1a\n")
    return path


class AuthTests(unittest.TestCase):
    def test_token_is_cached(self) -> None:
        t = FakeTransport()
        t.routes = {"tenant_access_token/internal": {"code": 0, "tenant_access_token": "tok-1"}}
        c = FeishuClient(app_id="id", app_secret="sec", transport=t)
        self.assertEqual(c.get_tenant_access_token(), "tok-1")
        self.assertEqual(c.get_tenant_access_token(), "tok-1")  # 命中缓存
        token_calls = [x for x in t.calls if x[0] == "post_json" and "tenant_access_token" in x[1]]
        self.assertEqual(len(token_calls), 1)

    def test_missing_credentials_raises_auth_error(self) -> None:
        c = FeishuClient(app_id="", app_secret="", transport=FakeTransport())
        with self.assertRaises(FeishuAuthError):
            c.get_tenant_access_token()

    def test_auth_error_is_runtime_error_subclass(self) -> None:
        # 兼容旧调用点：CRM 的 except RuntimeError 仍能捕获
        self.assertTrue(issubclass(FeishuAuthError, RuntimeError))
        self.assertTrue(issubclass(FeishuAPIError, RuntimeError))
        self.assertTrue(issubclass(FeishuHTTPError, RuntimeError))


class BitableTests(unittest.TestCase):
    def test_batch_create_chunks_and_counts(self) -> None:
        t = FakeTransport()
        t.routes = {
            "batch_create": {"code": 0, "data": {"records": [{"r": 1}, {"r": 2}]}},
        }
        c = FeishuClient(app_id="id", app_secret="sec", transport=t)
        records = [{"fields": {"a": i}} for i in range(1200)]
        written = c.batch_create_records("appT", "tbl", records, batch_size=500)
        create_calls = [x for x in t.calls if x[0] == "post_json" and "batch_create" in x[1]]
        self.assertEqual(len(create_calls), 3)  # 1200 / 500 → 3 块
        self.assertEqual(written, 6)  # 每块返回 2 条 × 3

    def test_batch_create_return_raw(self) -> None:
        from common.feishu import bitable

        t = FakeTransport()
        t.routes = {"batch_create": {"code": 0, "data": {"records": [{"record_id": "r1"}]}}}
        raw = bitable.batch_create_records(
            endpoint=None, token="tok", app_token="appT", table_id="tbl",
            records=[{"fields": {}}], transport=t, return_raw=True,
        )
        self.assertIsInstance(raw, dict)
        self.assertEqual(raw["data"]["records"][0]["record_id"], "r1")

    def test_list_tables_pagination(self) -> None:
        t = FakeTransport()
        # 为 tables 端点设置响应列表：第 1 次调用返回第 1 页，第 2 次返回第 2 页
        t.routes["tables"] = [
            {"code": 0, "tenant_access_token": "tok-1", "data": {"items": [{"id": 1}], "has_more": True, "page_token": "p2"}},
            {"code": 0, "tenant_access_token": "tok-1", "data": {"items": [{"id": 2}], "has_more": False}},
        ]
        c = FeishuClient(app_id="id", app_secret="sec", transport=t)
        tables = c.list_tables("appT")
        self.assertEqual([tb["id"] for tb in tables], [1, 2])

    def test_upload_drive_media(self) -> None:
        t = FakeTransport()
        t.routes = {"upload_all": {"code": 0, "data": {"file_token": "ft-1"}}}
        c = FeishuClient(app_id="id", app_secret="sec", transport=t)
        png = _png(Path(tempfile.gettempdir()) / "common_test.png")
        result = c.upload_drive_media("appT", png)
        self.assertEqual(result["file_token"], "ft-1")
        self.assertEqual(result["name"], "common_test.png")

    def test_missing_table_id_raises(self) -> None:
        from common.feishu import bitable

        with self.assertRaises(FeishuError):
            bitable.batch_create_records(
                endpoint=None, token="t", app_token="a", table_id="", records=[], transport=FakeTransport()
            )


class IMTests(unittest.TestCase):
    def test_upload_im_image_and_send(self) -> None:
        t = FakeTransport()
        t.routes = {
            "im/v1/images": {"code": 0, "data": {"image_key": "ik-1"}},
            "messages": {"code": 0, "data": {"message_id": "m-1"}},
        }
        c = FeishuClient(app_id="id", app_secret="sec", transport=t)
        png = _png(Path(tempfile.gettempdir()) / "common_im.png")
        image_key = c.upload_im_image(png)
        self.assertEqual(image_key, "ik-1")
        c.send_image_message("oc_chat", image_key)
        c.send_text_message("oc_chat", "hello")
        msg_calls = [x for x in t.calls if x[0] == "post_json" and "messages" in x[1]]
        self.assertEqual(len(msg_calls), 2)
        # 图片消息的 content 应序列化成 JSON 字符串且包含 image_key
        image_payload = msg_calls[0][2]
        self.assertIn(image_key, image_payload["content"])

    def test_send_message_requires_receive_id(self) -> None:
        from common.feishu import im

        with self.assertRaises(FeishuError):
            im.send_image_message(
                endpoint=None, token="t", receive_id="", image_key="ik", transport=FakeTransport()
            )


class HttpTests(unittest.TestCase):
    def test_normalize_endpoint(self) -> None:
        self.assertEqual(http.normalize_endpoint(None), "https://open.feishu.cn")
        self.assertEqual(http.normalize_endpoint("https://open.feishu.cn/"), "https://open.feishu.cn")

    def test_build_url(self) -> None:
        self.assertEqual(http.build_url("https://x/api", None), "https://x/api")
        self.assertIn("page_size=10", http.build_url("https://x/api", {"page_size": 10}))


if __name__ == "__main__":
    unittest.main()
