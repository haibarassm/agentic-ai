from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.audit import AuditLog, now_stamp  # noqa: E402
from src.browser_session import BrowserSession  # noqa: E402
from src.content_validator import ContentValidationError, load_content  # noqa: E402
from src.cloud_notify import CloudNotifier  # noqa: E402
from src.duplicate_guard import DuplicateGuard  # noqa: E402
from src.login_state import LoginState  # noqa: E402
from src.publisher import XhsPublisher, load_json  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Publish a Xiaohongshu image-text note through Playwright.")
    parser.add_argument("--content", required=True, help="Path to content JSON.")
    parser.add_argument("--mode", choices=["draft", "publish"], help="Override content mode.")
    parser.add_argument("--headless", action="store_true", help="Run browser headless. Not recommended for QR login.")
    parser.add_argument("--profile-dir", help="Persistent Chromium profile directory.")
    parser.add_argument("--runtime-dir", help="Runtime output directory.")
    parser.add_argument("--login-timeout", type=int, default=180, help="Seconds to wait for QR/login handoff.")
    parser.add_argument("--skip-duplicate-guard", action="store_true", help="Disable duplicate/frequency guard.")
    return parser.parse_args()


async def async_main() -> int:
    args = parse_args()
    app_config = load_json(PROJECT_ROOT / "config" / "app.json")
    selectors = load_json(PROJECT_ROOT / "config" / "selectors.json")
    notifier = CloudNotifier(app_config)

    runtime_dir = Path(args.runtime_dir or PROJECT_ROOT / app_config["default_runtime_dir"]).resolve()
    profile_dir = Path(args.profile_dir or PROJECT_ROOT / app_config["default_profile_dir"]).resolve()
    run_dir = runtime_dir / "runs" / now_stamp()
    audit = AuditLog(run_dir)

    try:
        content = load_content(Path(args.content).resolve(), mode_override=args.mode)
    except (ContentValidationError, json.JSONDecodeError) as exc:
        audit.event("content_invalid", error=str(exc))
        print(f"content invalid: {exc}", file=sys.stderr)
        return 2

    audit.write_json("content.normalized.json", content.to_jsonable())

    guard = DuplicateGuard(
        runtime_dir,
        min_interval_minutes=int(app_config.get("min_publish_interval_minutes", 10)),
    )
    if content.mode == "publish" and not args.skip_duplicate_guard:
        try:
            guard.check(content.fingerprint)
        except RuntimeError as exc:
            audit.event("duplicate_guard_blocked", error=str(exc))
            audit.write_json("result.json", {"status": "blocked", "reason": str(exc), "run_dir": str(run_dir)})
            print(f"blocked: {exc}", file=sys.stderr)
            return 3

    login_state = LoginState(
        runtime_dir,
        cache_hours=int(app_config.get("login_cache_hours", 12)),
    )

    result: dict[str, object]
    try:
        async with BrowserSession(
            profile_dir=profile_dir,
            headless=args.headless,
            audit=audit,
            debug_url_keywords=["publish", "note", "submit", "save", "draft", "topic", "activity", "creator"],
        ) as session:
            publisher = XhsPublisher(
                page=session.page,
                app_config=app_config,
                selectors=selectors,  # type: ignore[arg-type]
                login_state=login_state,
                audit=audit,
                login_timeout_seconds=args.login_timeout,
                notifier=notifier,
            )
            result = await publisher.run(content)
    except Exception as exc:  # noqa: BLE001 - CLI should return structured failure.
        audit.event("run_failed", error=str(exc), error_type=type(exc).__name__)
        result = {
            "status": "failed",
            "error": str(exc),
            "error_type": type(exc).__name__,
            "run_dir": str(run_dir),
        }
        audit.write_json("result.json", result)
        print(f"failed: {exc}", file=sys.stderr)
        return 1

    result["run_dir"] = str(run_dir)
    result["fingerprint"] = content.fingerprint
    audit.write_json("result.json", result)
    if content.mode == "publish" and result.get("status") == "published":
        guard.record(content.fingerprint, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    return asyncio.run(async_main())


if __name__ == "__main__":
    raise SystemExit(main())
