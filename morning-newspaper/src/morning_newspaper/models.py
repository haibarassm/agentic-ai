from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
from typing import Any, Dict


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def make_item_id(source_id: str, title: str, url: str) -> str:
    raw = f"{source_id}|{url}|{title}".encode("utf-8")
    return "sha1:" + hashlib.sha1(raw).hexdigest()


@dataclass
class RawItem:
    item_id: str
    source_id: str
    source_name: str
    source_group: str
    source_type: str
    title: str
    url: str
    published_at: str = ""
    raw_snippet: str = ""
    raw_metadata: Dict[str, Any] = field(default_factory=dict)
    fetched_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def raw_item_from_fields(
    *,
    source_id: str,
    source_name: str,
    source_group: str,
    source_type: str,
    title: str,
    url: str,
    published_at: str = "",
    raw_snippet: str = "",
    raw_metadata: Dict[str, Any] | None = None,
    fetched_at: str = "",
) -> RawItem:
    clean_title = " ".join(str(title or "").split()).strip()
    clean_url = str(url or "").strip()
    return RawItem(
        item_id=make_item_id(source_id, clean_title, clean_url),
        source_id=source_id,
        source_name=source_name,
        source_group=source_group,
        source_type=source_type,
        title=clean_title or "(untitled)",
        url=clean_url,
        published_at=published_at,
        raw_snippet=" ".join(str(raw_snippet or "").split()).strip(),
        raw_metadata=raw_metadata or {},
        fetched_at=fetched_at or utc_now_iso(),
    )
