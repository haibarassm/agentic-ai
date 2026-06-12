from __future__ import annotations

import argparse
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from morning_newspaper.common import load_env_file, load_yaml, write_json
from morning_newspaper.mailbox import collect_mailbox


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect mailbox reminders into queue and dashboard payload.")
    parser.add_argument("--config", default=str(PROJECT_ROOT / "config" / "sources.yaml"))
    parser.add_argument("--runtime", default=str(PROJECT_ROOT / "runtime"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config_path = Path(args.config)
    runtime_dir = Path(args.runtime)

    load_env_file(PROJECT_ROOT / ".env")
    config = load_yaml(config_path)
    mailbox_cfg = _mailbox_config(config)
    if not mailbox_cfg.get("enabled", False):
        payload = {
            "generated_at": "",
            "count": 0,
            "items": [],
            "status": "disabled",
        }
        write_json(runtime_dir / "executive_mailbox.json", payload)
        print("mailbox disabled")
        return

    result = collect_mailbox(mailbox_cfg, runtime_dir=runtime_dir)
    write_json(runtime_dir / "executive_mailbox.json", result.get("mailbox", {}))
    write_json(
        runtime_dir / "mailbox_collect_report.json",
        {
            "status": result.get("status", "unknown"),
            "reason": result.get("reason", ""),
            "queue_file": result.get("queue_file", ""),
            "queue_count": result.get("queue_count", 0),
            "alert_count": result.get("alert_count", 0),
        },
    )
    print(f"mailbox status={result.get('status', 'unknown')} alerts={result.get('alert_count', 0)}")
    print(f"wrote {runtime_dir / 'executive_mailbox.json'}")


def _mailbox_config(config: dict) -> dict:
    mailbox_cfg = config.get("assistant_mailbox", {})
    if isinstance(mailbox_cfg, dict) and mailbox_cfg:
        return mailbox_cfg
    return {}


if __name__ == "__main__":
    main()
