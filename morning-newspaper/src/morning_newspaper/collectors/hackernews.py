from __future__ import annotations

from typing import Any, Dict, List

from morning_newspaper.common import compact_text, fetch_json, normalize_unix, positive_int, strip_html
from morning_newspaper.models import RawItem, utc_now_iso

from .items import make_raw_item


def fetch_hackernews_top(source: Dict[str, Any]) -> List[RawItem]:
    endpoint = (compact_text(source.get("endpoint")) or "https://hacker-news.firebaseio.com/v0").rstrip("/")
    stories_type = compact_text(source.get("stories_type")) or "topstories"
    if stories_type not in {"topstories", "newstories", "beststories"}:
        stories_type = "topstories"
    max_items = positive_int(source.get("max_items"), 5)
    max_stories = positive_int(source.get("max_stories"), 20)
    timeout = positive_int(source.get("timeout_seconds"), 15)
    fetched_at = utc_now_iso()

    story_ids = fetch_json(f"{endpoint}/{stories_type}.json", timeout=timeout)
    if not isinstance(story_ids, list):
        return []

    items: List[RawItem] = []
    seen_urls: set[str] = set()
    for raw_id in story_ids[:max_stories]:
        if len(items) >= max_items:
            break
        try:
            story_id = int(raw_id)
        except (TypeError, ValueError):
            continue

        story = fetch_json(f"{endpoint}/item/{story_id}.json", timeout=timeout)
        if not isinstance(story, dict) or compact_text(story.get("type")) not in {"story", "job"}:
            continue

        url = compact_text(story.get("url")) or f"https://news.ycombinator.com/item?id={story_id}"
        if url in seen_urls:
            continue
        seen_urls.add(url)

        items.append(make_raw_item(
            source,
            title=compact_text(story.get("title")) or f"HN story #{story_id}",
            url=url,
            raw_snippet=strip_html(compact_text(story.get("text"))),
            published_at=normalize_unix(story.get("time"), fetched_at),
            fetched_at=fetched_at,
            raw_metadata={
                "story_id": story_id,
                "score": int(story.get("score", 0) or 0),
                "comments": int(story.get("descendants", 0) or 0),
                "author": compact_text(story.get("by")),
                "hn_url": f"https://news.ycombinator.com/item?id={story_id}",
                "stories_type": stories_type,
            },
        ))
    return items
