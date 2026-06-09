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
    parser = argparse.ArgumentParser(description="Apply selected titles to content_enriched.json and build shortlist.")
    parser.add_argument("--input", default=str(PROJECT_ROOT / "runtime" / "content_enriched.json"))
    parser.add_argument("--selected", default=str(PROJECT_ROOT / "runtime" / "title_shortlist_result.json"))
    parser.add_argument("--output", default=str(PROJECT_ROOT / "runtime" / "shortlist.json"))
    parser.add_argument("--report", default=str(PROJECT_ROOT / "runtime" / "shortlist_preview.md"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    selected_path = Path(args.selected)
    if not input_path.exists():
        raise SystemExit(f"input not found: {input_path}")
    if not selected_path.exists():
        raise SystemExit(f"selected titles file not found: {selected_path}")

    if selected_path.stat().st_mtime < input_path.stat().st_mtime:
        raise SystemExit(
            f"{selected_path.name} is older than {input_path.name} — stale result from a previous run, please regenerate"
        )

    input_payload = json.loads(input_path.read_text(encoding="utf-8"))
    selected_payload = json.loads(selected_path.read_text(encoding="utf-8"))
    items = input_payload.get("items", []) if isinstance(input_payload, dict) else []
    ranked_titles = []
    if isinstance(selected_payload, dict):
        ranked_titles = selected_payload.get("ranked_titles", []) or selected_payload.get("selected_titles", [])
    if not isinstance(items, list) or not isinstance(ranked_titles, list):
        raise SystemExit("invalid input format")

    selected_map = {str(t).strip(): idx for idx, t in enumerate(ranked_titles, 1) if str(t).strip()}

    shortlist: List[Dict[str, Any]] = []
    seen_titles: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip()
        rank = selected_map.get(title)
        if rank is None or not title or title in seen_titles:
            continue
        seen_titles.add(title)
        row = dict(item)
        row["shortlist_rank"] = rank
        shortlist.append(row)

    shortlist.sort(key=lambda row: int(row.get("shortlist_rank", 10**9)))
    shortlist = _apply_source_diversity(shortlist, items)
    write_json(Path(args.output), {
        "generated_at": utc_now_iso(),
        "input": str(input_path),
        "selected_titles_file": str(selected_path),
        "count": len(shortlist),
        "items": shortlist,
    })
    write_text(Path(args.report), _render_report(shortlist, ranked_titles))
    print(f"shortlist items={len(shortlist)}")
    print(f"wrote {args.output}")


def _apply_source_diversity(shortlist: List[Dict[str, Any]], all_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not shortlist:
        return shortlist

    source_type_present = {str(row.get("source_type", "")).strip() for row in shortlist if isinstance(row, dict)}
    if "github_high_stars" in source_type_present and "hackernews_top" in source_type_present:
        return shortlist

    shortlist_titles = {str(row.get("title", "")).strip() for row in shortlist if isinstance(row, dict)}
    candidates_by_source: Dict[str, List[Dict[str, Any]]] = {}
    for item in all_items:
        if not isinstance(item, dict):
            continue
        source_type = str(item.get("source_type", "")).strip()
        title = str(item.get("title", "")).strip()
        if not source_type or not title or title in shortlist_titles:
            continue
        candidates_by_source.setdefault(source_type, []).append(item)

    protected_sources = ["github_high_stars", "hackernews_top"]
    additions: List[Dict[str, Any]] = []
    max_rank = max((int(row.get("shortlist_rank", 0) or 0) for row in shortlist), default=0)
    for source_type in protected_sources:
        if source_type in source_type_present:
            continue
        pool = candidates_by_source.get(source_type, [])
        if not pool:
            continue
        chosen = None
        for item in pool:
            title = str(item.get("title", "")).strip().lower()
            if any(token in title for token in ["ai", "agent", "model", "llm", "code", "research"]):
                chosen = item
                break
        if chosen is None:
            chosen = pool[0]
        row = dict(chosen)
        max_rank += 1
        row["shortlist_rank"] = max_rank
        additions.append(row)

    if not additions:
        return shortlist

    merged = shortlist + additions
    merged.sort(key=lambda row: int(row.get("shortlist_rank", 10**9)))
    return merged


def _render_report(items: List[Dict[str, Any]], selected_titles: List[str]) -> str:
    lines = [
        "# Shortlist Preview",
        "",
        f"- generated_at: {utc_now_iso()}",
        f"- selected_titles: {len(selected_titles)}",
        f"- matched_items: {len(items)}",
        "",
    ]
    for item in items:
        lines.append(
            f"{item.get('shortlist_rank', '')}. [{item.get('source_type', '')}] "
            f"{item.get('title', '')} ({item.get('fetch_status', '')}, len={item.get('body_length', 0)})"
        )
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
