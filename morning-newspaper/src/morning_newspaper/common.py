from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import json
from pathlib import Path
import re
from typing import Any, Dict

import requests
import yaml


USER_AGENT = "Morning-Newspaper-Assistant/1.0"


def load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    ensure_dir(path.parent)
    path.write_text(text, encoding="utf-8")


def fetch_text(url: str, *, headers: Dict[str, str] | None = None, timeout: int = 20) -> str:
    request_headers = {"User-Agent": USER_AGENT}
    if headers:
        request_headers.update(headers)
    response = requests.get(url, headers=request_headers, timeout=timeout)
    response.raise_for_status()
    if response.content.startswith(b"\xef\xbb\xbf"):
        response.encoding = "utf-8-sig"
    if not response.encoding:
        response.encoding = response.apparent_encoding or "utf-8"
    return response.text


def fetch_json(url: str, *, headers: Dict[str, str] | None = None, timeout: int = 20) -> Any:
    request_headers = {"User-Agent": USER_AGENT}
    if headers:
        request_headers.update(headers)
    response = requests.get(url, headers=request_headers, timeout=timeout)
    response.raise_for_status()
    return response.json()


def normalize_iso(value: str | None, fallback: str = "") -> str:
    raw = str(value or "").strip()
    if not raw:
        return fallback
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        try:
            parsed = parsedate_to_datetime(raw)
        except (TypeError, ValueError):
            return fallback
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def normalize_unix(value: Any, fallback: str = "") -> str:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return datetime.fromtimestamp(parsed, tz=timezone.utc).replace(microsecond=0).isoformat()


def compact_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def strip_html(value: str) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", " ", value or "", flags=re.IGNORECASE)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;|&#160;", " ", text)
    return compact_text(text)


def positive_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, parsed)


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'\"")
        if key:
            import os
            os.environ.setdefault(key, value)
