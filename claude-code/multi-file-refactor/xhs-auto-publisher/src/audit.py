from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def now_stamp() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y%m%d-%H%M%S")


class AuditLog:
    def __init__(self, run_dir: Path) -> None:
        self.run_dir = run_dir
        self.screenshots_dir = run_dir / "screenshots"
        self.dom_dir = run_dir / "dom"
        self.actions_path = run_dir / "actions.jsonl"
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        self.dom_dir.mkdir(parents=True, exist_ok=True)

    def event(self, action: str, **fields: Any) -> None:
        payload = {
            "ts": datetime.now(timezone.utc).astimezone().isoformat(),
            "action": action,
            **fields,
        }
        with self.actions_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")

    async def screenshot(self, page: Any, name: str, *, full_page: bool = True) -> Path:
        path = self.screenshots_dir / f"{name}.png"
        try:
            await page.screenshot(path=str(path), full_page=full_page)
            self.event("screenshot", name=name, path=str(path))
        except Exception as exc:  # noqa: BLE001 - audit should not mask original flow.
            self.event("screenshot_failed", name=name, error=str(exc))
        return path

    async def dom_snapshot(self, page: Any, name: str) -> Path:
        path = self.dom_dir / f"{name}.html"
        try:
            content = await page.content()
            path.write_text(content, encoding="utf-8")
            self.event("dom_snapshot", name=name, path=str(path))
        except Exception as exc:  # noqa: BLE001
            self.event("dom_snapshot_failed", name=name, error=str(exc))
        return path

    def write_json(self, name: str, payload: Any) -> Path:
        path = self.run_dir / name
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self.event("write_json", name=name, path=str(path))
        return path
