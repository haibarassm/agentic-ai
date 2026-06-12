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


BODY_LIMIT = 1800

PROMPT_TEXT = """你是中文 AI 早报编辑。

下面我会给你若干条 shortlist 候选，每条都包含标题、来源、发布时间，以及正文前 1800 字以内的内容。
请基于这些信息，为每条内容生成一版中文早报草稿。

要求：
1. 只根据提供的标题和正文内容写，不要猜测正文之外的信息。
2. summary_main 要直接写“这条内容讲了什么”，不要写空话。
3. 如果证据不足，就保守表达，不要硬编。
4. 输出保持简洁，像中文科技早报，不像论文摘要。

只输出 JSON，格式如下：

{
  "drafts": [
    {
      "title": "原标题",
      "title_zh": "中文标题",
      "summary_main": "2到3句中文摘要",
      "published_at": "原始发布时间",
      "url": "原始访问链接"
    }
  ]
}
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare model input for draft generation from shortlist.")
    parser.add_argument("--input", default=str(PROJECT_ROOT / "runtime" / "shortlist.json"))
    parser.add_argument("--output", default=str(PROJECT_ROOT / "runtime" / "draft_input.json"))
    parser.add_argument("--prompt-txt", default=str(PROJECT_ROOT / "runtime" / "draft_prompt.txt"))
    parser.add_argument("--preview-md", default=str(PROJECT_ROOT / "runtime" / "draft_input_preview.md"))
    parser.add_argument("--body-limit", type=int, default=BODY_LIMIT)
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

    draft_items = [_to_draft_input(item, body_limit=args.body_limit) for item in items if isinstance(item, dict)]
    write_json(Path(args.output), {
        "generated_at": utc_now_iso(),
        "input": str(input_path),
        "count": len(draft_items),
        "body_limit": args.body_limit,
        "items": draft_items,
    })
    write_text(Path(args.prompt_txt), PROMPT_TEXT)
    write_text(Path(args.preview_md), _render_preview(draft_items))

    print(f"draft input items={len(draft_items)}")
    print(f"wrote {args.output}")
    print(f"wrote {args.prompt_txt}")


def _to_draft_input(item: Dict[str, Any], *, body_limit: int) -> Dict[str, Any]:
    body_text = str(item.get("body_text", "") or "").strip()
    model_input_text = body_text[:body_limit].strip()
    return {
        "shortlist_rank": item.get("shortlist_rank"),
        "item_id": str(item.get("item_id", "")).strip(),
        "title": str(item.get("title", "")).strip(),
        "source_type": str(item.get("source_type", "")).strip(),
        "source_name": str(item.get("source_name", "")).strip(),
        "published_at": str(item.get("published_at", "")).strip(),
        "url": str(item.get("url", "")).strip(),
        "fetch_status": str(item.get("fetch_status", "")).strip(),
        "body_length": int(item.get("body_length", 0) or 0),
        "model_input_text": model_input_text,
        "model_input_length": len(model_input_text),
    }


def _render_preview(items: List[Dict[str, Any]]) -> str:
    lines = [
        "# Draft Input Preview",
        "",
        f"- generated_at: {utc_now_iso()}",
        f"- count: {len(items)}",
        "",
    ]
    for item in items:
        lines.append(
            f"{item.get('shortlist_rank', '')}. [{item.get('source_type', '')}] "
            f"{item.get('title', '')} (input_len={item.get('model_input_length', 0)})"
        )
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
