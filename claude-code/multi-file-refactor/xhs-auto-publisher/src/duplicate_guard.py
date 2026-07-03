from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


class DuplicateGuard:
    def __init__(self, runtime_dir: Path, *, min_interval_minutes: int = 10) -> None:
        self.path = runtime_dir / "published_history.json"
        self.min_interval_minutes = min_interval_minutes
        runtime_dir.mkdir(parents=True, exist_ok=True)

    def check(self, fingerprint: str) -> None:
        payload = self._read()
        entries = payload.get("entries", [])
        if any(entry.get("fingerprint") == fingerprint for entry in entries):
            raise RuntimeError("duplicate content fingerprint; refusing to publish the same post twice")

        last_published_at = _parse_dt(payload.get("last_published_at"))
        if last_published_at:
            next_allowed = last_published_at + timedelta(minutes=self.min_interval_minutes)
            if datetime.now(timezone.utc).astimezone() < next_allowed:
                raise RuntimeError(f"publish interval guard active; next publish allowed after {next_allowed.isoformat()}")

    def record(self, fingerprint: str, result: dict[str, Any]) -> None:
        payload = self._read()
        now = datetime.now(timezone.utc).astimezone().isoformat()
        entries = payload.get("entries", [])
        entries.append(
            {
                "fingerprint": fingerprint,
                "published_at": now,
                "result": result,
            }
        )
        payload["last_published_at"] = now
        payload["entries"] = entries[-200:]
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"entries": []}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8-sig"))
        except Exception:
            return {"entries": []}
        return payload if isinstance(payload, dict) else {"entries": []}


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
