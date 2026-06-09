from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Dict, List


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from morning_newspaper.common import write_json, write_text
from morning_newspaper.models import utc_now_iso


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply draft generation results to draft_input.json.")
    parser.add_argument("--input", default=str(PROJECT_ROOT / "runtime" / "draft_input.json"))
    parser.add_argument("--result", default=str(PROJECT_ROOT / "runtime" / "draft_result.json"))
    parser.add_argument("--output", default=str(PROJECT_ROOT / "runtime" / "drafted_items.json"))
    parser.add_argument("--report", default=str(PROJECT_ROOT / "runtime" / "drafted_items_preview.md"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    result_path = Path(args.result)
    if not input_path.exists():
        raise SystemExit(f"input not found: {input_path}")
    if not result_path.exists():
        raise SystemExit(f"draft result file not found: {result_path}")

    if result_path.stat().st_mtime < input_path.stat().st_mtime:
        raise SystemExit(
            f"{result_path.name} is older than {input_path.name} — stale result from a previous run, please regenerate"
        )

    input_payload = json.loads(input_path.read_text(encoding="utf-8"))
    result_payload = json.loads(result_path.read_text(encoding="utf-8"))
    input_items = input_payload.get("items", []) if isinstance(input_payload, dict) else []
    drafts = result_payload.get("drafts", []) if isinstance(result_payload, dict) else []
    if not isinstance(input_items, list) or not isinstance(drafts, list):
        raise SystemExit("invalid input format")

    rank_input_map = {
        str(item.get("rank_id", "")).strip(): item
        for item in input_items
        if isinstance(item, dict) and str(item.get("rank_id", "")).strip()
    }
    if not rank_input_map:
        rank_input_map = {
            f"ID{item.get('shortlist_rank')}": item
            for item in input_items
            if isinstance(item, dict) and item.get("shortlist_rank") is not None
        }
    title_input_map = {
        str(item.get("title", "")).strip(): item
        for item in input_items
        if isinstance(item, dict) and str(item.get("title", "")).strip()
    }

    valid_rank_ids = set(rank_input_map.keys())
    valid_titles = set(title_input_map.keys())
    draft_rank_ids = [str(draft.get("rank_id", "")).strip() for draft in drafts if isinstance(draft, dict) and str(draft.get("rank_id", "")).strip()]
    draft_titles = [str(draft.get("title", "")).strip() for draft in drafts if isinstance(draft, dict) and str(draft.get("title", "")).strip()]
    rank_matches = [rank_id for rank_id in draft_rank_ids if rank_id in valid_rank_ids]
    title_matches = [title for title in draft_titles if title in valid_titles]
    if drafts and not rank_matches and not title_matches:
        raise SystemExit("draft results appear stale or mismatched: no draft entries match current input by rank_id or title")

    drafted_items: List[Dict[str, Any]] = []
    seen_keys: set[str] = set()
    for draft in drafts:
        if not isinstance(draft, dict):
            continue
        rank_id = str(draft.get("rank_id", "")).strip()
        title = str(draft.get("title", "")).strip()
        dedupe_key = rank_id or title
        if not dedupe_key or dedupe_key in seen_keys:
            continue
        source_item = rank_input_map.get(rank_id) if rank_id else None
        if not source_item and title:
            source_item = title_input_map.get(title)
        if not source_item:
            continue
        seen_keys.add(dedupe_key)
        drafted_items.append(_merge_item(source_item, draft))

    drafted_items.sort(key=lambda row: int(row.get("shortlist_rank", 10**9)))
    write_json(Path(args.output), {
        "generated_at": utc_now_iso(),
        "input": str(input_path),
        "draft_result_file": str(result_path),
        "count": len(drafted_items),
        "items": drafted_items,
    })
    write_text(Path(args.report), _render_report(drafted_items, len(drafts)))
    print(f"drafted items={len(drafted_items)}")
    print(f"wrote {args.output}")


def _merge_item(source_item: Dict[str, Any], draft: Dict[str, Any]) -> Dict[str, Any]:
    source_title = str(source_item.get("title", "")).strip()
    shortlist_rank = source_item.get("shortlist_rank")
    source_rank_id = str(source_item.get("rank_id", "")).strip()
    draft_rank_id = str(draft.get("rank_id", "")).strip()
    rank_id = source_rank_id or draft_rank_id or (f"ID{shortlist_rank}" if shortlist_rank is not None else "")
    return {
        "shortlist_rank": shortlist_rank,
        "rank_id": rank_id,
        "item_id": str(source_item.get("item_id", "")).strip(),
        "title": source_title,
        "title_zh": str(draft.get("title_zh", "")).strip() or source_title,
        "summary_main": str(draft.get("summary_main", "")).strip(),
        "published_at": str(draft.get("published_at", "")).strip() or str(source_item.get("published_at", "")).strip(),
        "url": str(draft.get("url", "")).strip() or str(source_item.get("url", "")).strip(),
        "source_type": str(source_item.get("source_type", "")).strip(),
        "source_name": str(source_item.get("source_name", "")).strip(),
    }


def _render_report(items: List[Dict[str, Any]], draft_count: int) -> str:
    lines = [
        "# Drafted Items Preview",
        "",
        f"- generated_at: {utc_now_iso()}",
        f"- draft_results: {draft_count}",
        f"- matched_items: {len(items)}",
        "",
    ]
    for item in items:
        lines.append(
            f"{item.get('shortlist_rank', '')}. {item.get('title_zh', '') or item.get('title', '')} "
            f"({item.get('published_at', '')})"
        )
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
