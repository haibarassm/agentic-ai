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


PROMPT_TEXT = """你是 AI 早报编辑。

下面我会给你一组已经完成中文草稿的候选条目。每条都带有稳定 ID（rank_id / item_id）。请你基于内容质量和主题匹配度，选出最终 Top10，并给出排序。

我们的主题是：AI 最新的技术进展和商业化落地。

排序时优先考虑：
1. 是否和 AI 技术进展、模型、Agent、产品发布、开源工具、企业采用、融资并购直接相关。
2. 内容本身是否清楚、完整、像一条可以进入早报的新闻。
3. 哪些内容更适合排在前面，哪些内容更适合作为后位补充。

不要猜测草稿之外的信息。
如果不足 10 条，就按实际数量输出。
优先按 rank_id 输出；如果实在不方便，也可以输出 item_id。不要只返回标题。
只输出 JSON，格式如下二选一：

{
  "top10_rank_ids": ["ID1", "ID2"]
}

或

{
  "top10_item_ids": ["sha1:...", "sha1:..."]
}
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare ranking input for final Top10 selection.")
    parser.add_argument("--input", default=str(PROJECT_ROOT / "runtime" / "drafted_items.json"))
    parser.add_argument("--output", default=str(PROJECT_ROOT / "runtime" / "top10_ranking_input.json"))
    parser.add_argument("--prompt-txt", default=str(PROJECT_ROOT / "runtime" / "top10_ranking_prompt.txt"))
    parser.add_argument("--preview-md", default=str(PROJECT_ROOT / "runtime" / "top10_ranking_preview.md"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    if not input_path.exists():
        raise SystemExit(f"input not found: {input_path}")

    payload = json.loads(input_path.read_text(encoding="utf-8"))
    items = payload.get("items", []) if isinstance(payload, dict) else []
    if not isinstance(items, list):
        raise SystemExit("input JSON must contain an items list")

    ranking_items = [_to_ranking_item(item) for item in items if isinstance(item, dict)]
    write_json(Path(args.output), {
        "generated_at": utc_now_iso(),
        "input": str(input_path),
        "count": len(ranking_items),
        "items": ranking_items,
    })
    write_text(Path(args.prompt_txt), PROMPT_TEXT)
    write_text(Path(args.preview_md), _render_preview(ranking_items))

    print(f"ranking items={len(ranking_items)}")
    print(f"wrote {args.output}")
    print(f"wrote {args.prompt_txt}")


def _to_ranking_item(item: Dict[str, Any]) -> Dict[str, Any]:
    shortlist_rank = item.get("shortlist_rank")
    rank_id = f"ID{shortlist_rank}" if shortlist_rank is not None else ""
    return {
        "rank_id": rank_id,
        "item_id": str(item.get("item_id", "")).strip(),
        "title": str(item.get("title", "")).strip(),
        "title_zh": str(item.get("title_zh", "")).strip(),
        "summary_main": str(item.get("summary_main", "")).strip(),
        "source_type": str(item.get("source_type", "")).strip(),
        "source_name": str(item.get("source_name", "")).strip(),
        "published_at": str(item.get("published_at", "")).strip(),
        "url": str(item.get("url", "")).strip(),
    }


def _render_preview(items: List[Dict[str, Any]]) -> str:
    lines = [
        "# Top10 Ranking Preview",
        "",
        f"- generated_at: {utc_now_iso()}",
        f"- count: {len(items)}",
        "",
    ]
    for idx, item in enumerate(items, 1):
        lines.append(
            f"{idx}. {item.get('rank_id', '')} | {item.get('item_id', '')} | "
            f"{item.get('title_zh', '') or item.get('title', '')} "
            f"[{item.get('source_type', '')}]"
        )
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
