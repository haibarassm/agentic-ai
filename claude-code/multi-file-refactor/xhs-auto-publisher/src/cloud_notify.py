from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Lesson 17：让 cloud_notify 能直接用共享 FeishuClient 发二维码到飞书群。
# 这里只把 multi-file-refactor/ 加到 sys.path；FeishuClient 本身懒导入，
# 不配飞书凭证（默认走龙虾）时不会触发 import，保持向后兼容。
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# 支持的投递模式
LOBSTER_CHANNEL = "lobster_channel"
FEISHU_CLIENT = "feishu_client"


class CloudNotifier:
    def __init__(self, app_config: dict[str, Any]) -> None:
        self.app_config = app_config

    def qr_handoff_enabled(self) -> bool:
        mode = str(self.app_config.get("notify_qr_via", "none")).lower()
        return mode in {LOBSTER_CHANNEL, FEISHU_CLIENT}

    def notify_qr(self, screenshot_path: Path, *, run_dir: Path) -> None:
        mode = str(self.app_config.get("notify_qr_via", "none")).lower()
        if mode == LOBSTER_CHANNEL:
            self._emit_lobster_channel_payload(screenshot_path, run_dir=run_dir)
            return
        if mode == FEISHU_CLIENT:
            self._deliver_via_feishu_client(screenshot_path, run_dir=run_dir)
            return
        raise RuntimeError(f"Unsupported cloud notify mode: {mode}")

    # ---- 模式一：龙虾代发（默认，向后兼容）----------------------------------
    def _emit_lobster_channel_payload(self, screenshot_path: Path, *, run_dir: Path) -> None:
        notify_dir = self._notify_dir(run_dir)
        notify_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "ts": datetime.now(timezone.utc).astimezone().isoformat(),
            "channel": LOBSTER_CHANNEL,
            "kind": "login_qr",
            "platform": str(self.app_config.get("platform", "xiaohongshu")),
            "title": f"{self._title_prefix()} 小红书登录二维码",
            "run_id": run_dir.name,
            "screenshot_path": str(screenshot_path),
            "message_lines": self._build_message_lines(screenshot_path, run_dir=run_dir),
            "action": "send_image_to_feishu_group",
            "delivery": {
                "type": "image_file",
                "path": str(screenshot_path),
                "caption_lines": self._build_message_lines(screenshot_path, run_dir=run_dir),
            },
        }
        path = notify_dir / "login_qr.payload.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---- 模式二：直接用共享 FeishuClient 发图（Lesson 17 新增）----------------
    def _deliver_via_feishu_client(self, screenshot_path: Path, *, run_dir: Path) -> None:
        from common.feishu import FeishuClient, FeishuError  # 懒导入：不配凭证时不触发

        app_id, app_secret, receive_id, receive_id_type, endpoint = self._resolve_feishu_creds()
        missing = [
            name
            for name, value in (
                ("FEISHU_APP_ID", app_id),
                ("FEISHU_APP_SECRET", app_secret),
                ("FEISHU_RECEIVE_ID", receive_id),
            )
            if not value
        ]
        if missing:
            raise RuntimeError(
                "feishu_client 模式缺少配置: " + ", ".join(missing)
                + "（请在 app.json 或环境变量中提供）"
            )

        client = FeishuClient(app_id=app_id, app_secret=app_secret, endpoint=endpoint)
        image_key = client.upload_im_image(screenshot_path)
        client.send_image_message(receive_id, image_key, receive_id_type=receive_id_type)

        # 图片已送达（关键路径完成）；文字说明为尽力而为，失败不阻断主流程
        caption = "\n".join(self._build_message_lines(screenshot_path, run_dir=run_dir))
        caption_error = ""
        try:
            client.send_text_message(receive_id, caption, receive_id_type=receive_id_type)
        except FeishuError as exc:
            caption_error = str(exc)

        self._write_delivery_record(
            screenshot_path,
            run_dir=run_dir,
            image_key=image_key,
            receive_id=receive_id,
            receive_id_type=receive_id_type,
            caption_error=caption_error,
        )

    def _resolve_feishu_creds(self) -> tuple[str, str, str, str, str]:
        """从 app_config（优先）或环境变量解析飞书直发配置。"""

        def pick(cfg_key: str, env_key: str, default: str = "") -> str:
            value = str(self.app_config.get(cfg_key, "")).strip()
            if value:
                return value
            return os.environ.get(env_key, "").strip() or default

        receive_id_type = str(self.app_config.get("feishu_receive_id_type", "chat_id")).strip() or "chat_id"
        endpoint = pick("feishu_endpoint", "FEISHU_ENDPOINT", "https://open.feishu.cn")
        return (
            pick("feishu_app_id", "FEISHU_APP_ID"),
            pick("feishu_app_secret", "FEISHU_APP_SECRET"),
            pick("feishu_receive_id", "FEISHU_RECEIVE_ID"),
            receive_id_type,
            endpoint,
        )

    def _write_delivery_record(
        self,
        screenshot_path: Path,
        *,
        run_dir: Path,
        image_key: str,
        receive_id: str,
        receive_id_type: str,
        caption_error: str,
    ) -> None:
        notify_dir = self._notify_dir(run_dir)
        notify_dir.mkdir(parents=True, exist_ok=True)
        record = {
            "ts": datetime.now(timezone.utc).astimezone().isoformat(),
            "channel": FEISHU_CLIENT,
            "kind": "login_qr",
            "platform": str(self.app_config.get("platform", "xiaohongshu")),
            "title": f"{self._title_prefix()} 小红书登录二维码",
            "run_id": run_dir.name,
            "screenshot_path": str(screenshot_path),
            "image_key": image_key,
            "receive_id": receive_id,
            "receive_id_type": receive_id_type,
            "action": "sent_image_to_feishu_via_feishuclient",
            "caption_error": caption_error,
        }
        path = notify_dir / "login_qr.feishu_delivery.json"
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---- 公共辅助 ----------------------------------------------------------
    def _notify_dir(self, run_dir: Path) -> Path:
        configured = str(self.app_config.get("lobster_notify_dir", "runtime/lobster-notify")).strip()
        base = Path(configured)
        if not base.is_absolute():
            base = run_dir.parent.parent / base.name
        return base / run_dir.name

    def _title_prefix(self) -> str:
        return str(self.app_config.get("feishu_title_prefix", "[XHS Cloud Login]")).strip() or "[XHS Cloud Login]"

    def _build_message_lines(self, screenshot_path: Path, *, run_dir: Path) -> list[str]:
        return [
            f"{self._title_prefix()} 小红书登录二维码",
            f"Run ID: {run_dir.name}",
            f"图片路径: {screenshot_path}",
            "请扫码完成登录，扫码后等待任务自动继续。",
        ]
