from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


class LoginState:
    def __init__(self, runtime_dir: Path, *, cache_hours: int = 12, account: str = "default") -> None:
        self.runtime_dir = runtime_dir
        self.cache_hours = cache_hours
        self.account = account
        self.path = runtime_dir / "login_cache.json"
        self.runtime_dir.mkdir(parents=True, exist_ok=True)

    def is_valid(self) -> bool:
        payload = self._read()
        if not payload:
            return False
        if payload.get("platform") != "xiaohongshu" or payload.get("account") != self.account:
            return False
        if not payload.get("is_logged_in"):
            return False
        expires_at = _parse_dt(payload.get("expires_at"))
        return bool(expires_at and expires_at > datetime.now(timezone.utc).astimezone())

    def mark_logged_in(self, *, home_url: str) -> None:
        now = datetime.now(timezone.utc).astimezone()
        payload = {
            "platform": "xiaohongshu",
            "account": self.account,
            "is_logged_in": True,
            "checked_at": now.isoformat(),
            "expires_at": (now + timedelta(hours=self.cache_hours)).isoformat(),
            "home_url": home_url,
        }
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def invalidate(self) -> None:
        payload = self._read() or {}
        payload.update(
            {
                "platform": "xiaohongshu",
                "account": self.account,
                "is_logged_in": False,
                "checked_at": datetime.now(timezone.utc).astimezone().isoformat(),
            }
        )
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _read(self) -> dict[str, Any] | None:
        if not self.path.exists():
            return None
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return None
        return payload if isinstance(payload, dict) else None


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc).astimezone()
    return dt.astimezone()
