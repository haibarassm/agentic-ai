from __future__ import annotations

from typing import Any, Dict, List
import xml.etree.ElementTree as ET

from morning_newspaper.common import compact_text, fetch_text, normalize_iso, positive_int, strip_html
from morning_newspaper.models import RawItem, utc_now_iso

from .items import make_raw_item


def fetch_rss(source: Dict[str, Any]) -> List[RawItem]:
    url = compact_text(source.get("url"))
    if not url:
        return []
    max_items = positive_int(source.get("max_items"), 5)
    fetched_at = utc_now_iso()
    text = fetch_text(url, timeout=20)
    root = ET.fromstring(text)
    entries = root.findall(".//item") or root.findall(".//{http://www.w3.org/2005/Atom}entry")

    items: List[RawItem] = []
    for entry in entries[:max_items]:
        title = _xml_text(entry, "title") or _xml_text(entry, "{http://www.w3.org/2005/Atom}title")
        link = _xml_text(entry, "link")
        if not link:
            atom_link = entry.find("{http://www.w3.org/2005/Atom}link")
            link = compact_text(atom_link.get("href")) if atom_link is not None else ""
        snippet = (
            _xml_text(entry, "description")
            or _xml_text(entry, "summary")
            or _xml_text(entry, "{http://www.w3.org/2005/Atom}summary")
        )
        published = (
            _xml_text(entry, "pubDate")
            or _xml_text(entry, "published")
            or _xml_text(entry, "{http://www.w3.org/2005/Atom}published")
            or _xml_text(entry, "{http://www.w3.org/2005/Atom}updated")
        )
        if title or link:
            items.append(make_raw_item(
                source,
                title=title or "(untitled)",
                url=link,
                raw_snippet=strip_html(snippet),
                published_at=normalize_iso(published, fetched_at),
                fetched_at=fetched_at,
            ))
    return items


def _xml_text(entry: ET.Element, tag: str) -> str:
    element = entry.find(tag)
    return compact_text(element.text) if element is not None and element.text else ""
