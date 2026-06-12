from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from morning_newspaper.common import compact_text, write_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Execute tavily_search_plan.json and write tavily_search_results.json")
    parser.add_argument("--project-root", default=str(PROJECT_ROOT))
    parser.add_argument("--plan", default="")
    parser.add_argument("--output", default="")
    parser.add_argument("--python", default=sys.executable)
    return parser.parse_args()


def _utc_now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def main() -> None:
    args = parse_args()
    root = Path(args.project_root).resolve()
    runtime_dir = root / "runtime"
    plan_path = Path(args.plan).resolve() if args.plan else runtime_dir / "tavily_search_plan.json"
    output_path = Path(args.output).resolve() if args.output else runtime_dir / "tavily_search_results.json"

    if not plan_path.exists():
        raise FileNotFoundError(f"plan file not found: {plan_path}")

    payload = json.loads(plan_path.read_text(encoding="utf-8"))
    plan_items = payload.get("items", []) if isinstance(payload, dict) else []
    if not isinstance(plan_items, list):
        plan_items = []

    tavily_script = Path("/root/.openclaw/workspace/skills/openclaw-tavily-search/scripts/tavily_search.py")
    if not tavily_script.exists():
        raise FileNotFoundError(f"tavily script not found: {tavily_script}")

    out_items: List[Dict[str, Any]] = []
    runs: List[Dict[str, Any]] = []

    for item in plan_items:
        if not isinstance(item, dict):
            continue
        query = compact_text(item.get("query"))
        if not query:
            continue
        max_items = int(item.get("max_items") or 5)
        topic_id = compact_text(item.get("topic_id"))
        topic_name = compact_text(item.get("topic_name")) or topic_id
        domains = item.get("domains", []) if isinstance(item.get("domains"), list) else []
        domain_suffix = ""
        if domains:
            domain_suffix = " (site:" + " OR site:".join(domains) + ")"
        effective_query = query + domain_suffix

        cmd = [
            args.python,
            str(tavily_script),
            "--query", effective_query,
            "--max-results", str(max_items),
            "--format", "brave",
        ]
        completed = subprocess.run(cmd, cwd=str(root), text=True, capture_output=True, check=False)
        run_info: Dict[str, Any] = {
            "topic_id": topic_id,
            "topic_name": topic_name,
            "query": query,
            "effective_query": effective_query,
            "returncode": completed.returncode,
        }
        if completed.stderr.strip():
            run_info["stderr"] = completed.stderr.strip()

        results_count = 0
        if completed.returncode == 0:
            try:
                result_payload = json.loads(completed.stdout)
            except Exception as exc:
                run_info["parse_error"] = str(exc)
                result_payload = {}
            raw_results = result_payload.get("results", []) if isinstance(result_payload, dict) else []
            if isinstance(raw_results, list):
                for raw in raw_results:
                    if not isinstance(raw, dict):
                        continue
                    title = compact_text(raw.get("title"))
                    url = compact_text(raw.get("url"))
                    snippet = compact_text(raw.get("snippet") or raw.get("content"))
                    if not title or not url:
                        continue
                    out_items.append({
                        "topic_id": topic_id,
                        "topic_name": topic_name,
                        "query": query,
                        "source_name": "OpenClaw Tavily",
                        "source": "tavily-search",
                        "title": title,
                        "url": url,
                        "summary": snippet,
                        "published_at": compact_text(raw.get("published_at") or raw.get("published_date")),
                        "fetched_at": _utc_now_iso(),
                    })
                    results_count += 1
        run_info["results_count"] = results_count
        runs.append(run_info)

    deduped: List[Dict[str, Any]] = []
    seen_urls: set[str] = set()
    for item in out_items:
        url = item.get("url", "")
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        deduped.append(item)

    write_json(output_path, {
        "generated_at": _utc_now_iso(),
        "input": str(plan_path),
        "count": len(deduped),
        "items": deduped,
        "runs": runs,
    })
    print(f"tavily items={len(deduped)}")
    print(f"wrote {output_path}")


if __name__ == "__main__":
    main()
