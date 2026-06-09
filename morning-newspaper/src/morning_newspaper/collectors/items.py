from __future__ import annotations

from typing import Any, Dict, List

from morning_newspaper.common import compact_text
from morning_newspaper.models import RawItem, raw_item_from_fields


def make_raw_item(
    source: Dict[str, Any],
    *,
    title: str,
    url: str,
    raw_snippet: str = "",
    published_at: str = "",
    raw_metadata: Dict[str, Any] | None = None,
    fetched_at: str = "",
) -> RawItem:
    return raw_item_from_fields(
        source_id=compact_text(source.get("id") or source.get("source_id")),
        source_name=compact_text(source.get("source_name") or source.get("name")),
        source_group=compact_text(source.get("source_group")) or "primary",
        source_type=compact_text(source.get("source_type") or source.get("type")),
        title=title,
        url=url,
        published_at=published_at,
        raw_snippet=raw_snippet,
        raw_metadata=raw_metadata or {},
        fetched_at=fetched_at,
    )


def dedup_exact(items: List[RawItem]) -> List[RawItem]:
    out: List[RawItem] = []
    seen: set[str] = set()
    for item in items:
        key = item.url or item.item_id
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out
