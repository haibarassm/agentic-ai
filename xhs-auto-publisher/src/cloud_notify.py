from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class CloudNotifier:
    def __init__(self, app_config: dict[str, Any]) -> None:
        self.app_config = app_config

    def qr_handoff_enabled(self) -> bool:
        mode = str(self.app_config.get("notify_qr_via", "none")).lower()
        return mode == "lobster_channel"

    def notify_qr(self, screenshot_path: Path, *, run_dir: Path) -> None:
        mode = str(self.app_config.get("notify_qr_via", "none")).lower()
        if mode != "lobster_channel":
            raise RuntimeError(f"Unsupported cloud notify mode: {mode}")
        self._emit_lobster_channel_payload(screenshot_path, run_dir=run_dir)

    def _emit_lobster_channel_payload(self, screenshot_path: Path, *, run_dir: Path) -> None:
        notify_dir = self._notify_dir(run_dir)
        notify_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "ts": datetime.now(timezone.utc).astimezone().isoformat(),
            "channel": "lobster_channel",
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
            "请把这张二维码图片直接发到飞书群，用户扫码后等待任务继续。",
        ]
