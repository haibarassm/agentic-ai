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
请只根据下面这批候选标题，按“AI 最新的技术进展和商业化落地”这个主题做相关性排序。

优先考虑：
1. AI 技术、模型、Agent、产品发布、开源工具、企业采用、融资并购直接相关的标题。
2. 对今天的中文 AI 早报更有信息密度、更新价值和代表性的标题。
3. 不同来源、不同子主题的覆盖面，不要让候选池被同一来源或同一类重复内容占满。

明确要求：
- 这一步的目标不是把候选裁得很少，而是给后续 Top10 提供一个足够宽、足够多样的有序候选池。
- 尽量保留来自不同来源的代表项；如果 GitHub 高星项目或 Hacker News 热门故事中有明显相关项，应优先至少保留少量代表项，不要被单一来源全部挤出。
- 对完全重复、近似重复、同一页面不同搜索命中的标题，只保留最有代表性的一条，其余排到很后面或直接不选。
- 如果某个标题明显与 AI 主线无关，可以不选。

输出要求：
- 尽量返回前 15 条；如果高相关候选不足 15 条，可少于 15 条。
- 同标题不要重复返回。
- 只输出 JSON：

{
  "ranked_titles": ["标题1", "标题2"]
}
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare title-only shortlist input for the AI morning report.")
    parser.add_argument("--input", default=str(PROJECT_ROOT / "runtime" / "content_enriched.json"))
    parser.add_argument("--titles-json", default=str(PROJECT_ROOT / "runtime" / "title_candidates.json"))
    parser.add_argument("--prompt-txt", default=str(PROJECT_ROOT / "runtime" / "title_shortlist_prompt.txt"))
    parser.add_argument("--preview-md", default=str(PROJECT_ROOT / "runtime" / "title_candidates_preview.md"))
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

    candidates = [_to_title_candidate(item) for item in items if isinstance(item, dict)]
    candidates = [item for item in candidates if item["title"]]
    candidates = _dedupe_candidates(candidates)

    write_json(Path(args.titles_json), {
        "generated_at": utc_now_iso(),
        "input": str(input_path),
        "count": len(candidates),
        "titles": candidates,
    })
    write_text(Path(args.prompt_txt), PROMPT_TEXT)
    write_text(Path(args.preview_md), _render_preview(candidates))

    print(f"title candidates={len(candidates)}")
    print(f"wrote {args.titles_json}")
    print(f"wrote {args.prompt_txt}")


def _to_title_candidate(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "item_id": str(item.get("item_id", "")).strip(),
        "title": str(item.get("title", "")).strip(),
        "source_type": str(item.get("source_type", "")).strip(),
        "source_name": str(item.get("source_name", "")).strip(),
        "published_at": str(item.get("published_at", "")).strip(),
    }


def _dedupe_candidates(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    deduped: List[Dict[str, Any]] = []
    seen_titles: set[str] = set()
    for item in candidates:
        title = str(item.get("title", "")).strip()
        if not title or title in seen_titles:
            continue
        seen_titles.add(title)
        deduped.append(item)
    return deduped


def _render_preview(candidates: List[Dict[str, Any]]) -> str:
    lines = [
        "# Title Candidates",
        "",
        f"- generated_at: {utc_now_iso()}",
        f"- count: {len(candidates)}",
        "",
    ]
    for idx, item in enumerate(candidates, 1):
        lines.append(
            f"{idx}. [{item.get('source_type', '')}] {item.get('title', '')} "
            f"({item.get('published_at', '')})"
        )
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
