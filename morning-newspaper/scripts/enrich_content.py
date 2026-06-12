from __future__ import annotations

import argparse
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from morning_newspaper.common import write_json, write_text
from morning_newspaper.content_fetch import enrich_items_with_content
from morning_newspaper.models import utc_now_iso


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch clean article bodies for collected raw items.")
    parser.add_argument("--input", default=str(PROJECT_ROOT / "runtime" / "collected_raw.json"))
    parser.add_argument("--output", default=str(PROJECT_ROOT / "runtime" / "content_enriched.json"))
    parser.add_argument("--report", default=str(PROJECT_ROOT / "runtime" / "content_fetch_report.md"))
    parser.add_argument("--max-workers", type=int, default=4)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    if not input_path.exists():
        raise SystemExit(f"input not found: {input_path}")

    import json

    payload = json.loads(input_path.read_text(encoding="utf-8"))
    items = payload.get("items", []) if isinstance(payload, dict) else []
    if not isinstance(items, list):
        raise SystemExit("input JSON must contain an items list")

    enriched = enrich_items_with_content(items, max_workers=args.max_workers)
    output_payload = {
        "generated_at": utc_now_iso(),
        "input": str(input_path),
        "count": len(enriched),
        "items": enriched,
    }
    write_json(Path(args.output), output_payload)
    write_text(Path(args.report), _render_report(enriched))
    print(f"enriched items={len(enriched)}")
    print(f"wrote {args.output}")


def _render_report(items: list[dict]) -> str:
    ok = sum(1 for item in items if item.get("fetch_status") == "ok")
    lines = [
        "# Content Fetch Report",
        "",
        f"- total_items: {len(items)}",
        f"- ok: {ok}",
        f"- not_ok: {len(items) - ok}",
        "",
        "| source | status | method | length | title | note |",
        "| --- | --- | --- | ---: | --- | --- |",
    ]
    for item in items:
        title = str(item.get("title", "")).replace("|", "\\|")[:80]
        note = str(item.get("note", "")).replace("|", "\\|")[:100]
        lines.append(
            f"| {item.get('source_type', '')} | {item.get('fetch_status', '')} | "
            f"{item.get('extract_method', '')} | {item.get('body_length', 0)} | {title} | {note} |"
        )
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
