from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
from typing import Any, Dict, Iterable, List
from urllib.parse import urlencode

from morning_newspaper.common import compact_text, fetch_json, normalize_iso, positive_int
from morning_newspaper.models import RawItem, utc_now_iso

from .items import make_raw_item


def fetch_github_high_stars(source: Dict[str, Any]) -> List[RawItem]:
    endpoint = compact_text(source.get("endpoint")) or "https://api.github.com/search/repositories"
    max_items = positive_int(source.get("max_items"), 5)
    per_query_limit = positive_int(source.get("per_query_limit"), 10)
    fetched_at = utc_now_iso()
    items: List[RawItem] = []
    seen_urls: set[str] = set()

    for language, extra in _iter_query_specs(source):
        if len(items) >= max_items:
            break
        query = _build_query(source, language=language, extra=extra)
        params = {
            "q": query,
            "sort": "stars",
            "order": "desc",
            "per_page": max(1, min(100, per_query_limit)),
        }
        payload = fetch_json(
            f"{endpoint}?{urlencode(params)}",
            headers=_github_headers(compact_text(source.get("auth_env")) or None),
            timeout=positive_int(source.get("timeout_seconds"), 20),
        )
        repos = payload.get("items", []) if isinstance(payload, dict) else []
        if not isinstance(repos, list):
            continue

        for repo in repos:
            if len(items) >= max_items:
                break
            if not isinstance(repo, dict):
                continue
            url = compact_text(repo.get("html_url"))
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)

            full_name = compact_text(repo.get("full_name")) or "(unknown repo)"
            description = compact_text(repo.get("description"))
            items.append(make_raw_item(
                source,
                title=full_name,
                url=url,
                raw_snippet=description,
                published_at=normalize_iso(compact_text(repo.get("created_at")) or None, fetched_at),
                fetched_at=fetched_at,
                raw_metadata={
                    "query": query,
                    "stars": int(repo.get("stargazers_count", 0) or 0),
                    "forks": int(repo.get("forks_count", 0) or 0),
                    "language": compact_text(repo.get("language")),
                    "topics": repo.get("topics", []) if isinstance(repo.get("topics"), list) else [],
                    "pushed_at": compact_text(repo.get("pushed_at")),
                },
            ))
    return items


def _github_headers(auth_env: str | None) -> Dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if auth_env:
        token = os.getenv(auth_env, "").strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"
    return headers


def _build_query(source: Dict[str, Any], *, language: str | None = None, extra: str | None = None) -> str:
    since_days = positive_int(source.get("since_days"), 7)
    min_stars = positive_int(source.get("min_stars"), 80)
    since = (datetime.now(timezone.utc) - timedelta(days=since_days)).date().isoformat()
    parts = [
        f"created:>={since}",
        f"stars:>={min_stars}",
        "archived:false",
        "is:public",
    ]
    if language:
        parts.append(f"language:{language}")
    if extra:
        parts.append(extra)
    return " ".join(parts)


def _iter_query_specs(source: Dict[str, Any]) -> Iterable[tuple[str | None, str | None]]:
    emitted = False
    languages = source.get("languages", [])
    if isinstance(languages, list):
        for language in languages:
            text = compact_text(language)
            if text:
                emitted = True
                yield text, None
    extras = source.get("extra_queries", [])
    if isinstance(extras, list):
        for extra in extras:
            text = compact_text(extra)
            if text:
                emitted = True
                yield None, text
    if not emitted:
        yield None, None
