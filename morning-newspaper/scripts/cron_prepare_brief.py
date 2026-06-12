from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timezone

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNTIME = PROJECT_ROOT / 'runtime'
STATUS = RUNTIME / 'cron_status.json'
BRIEF = RUNTIME / 'cron_delivery_message.txt'


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def trim(text: str, limit: int) -> str:
    text = ' '.join(str(text or '').split()).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip(' ，,；;。') + '…'


def main() -> int:
    status = load_json(STATUS)
    publishable = load_json(RUNTIME / 'top10_publishable.json')
    items = publishable.get('items', []) if isinstance(publishable.get('items'), list) else []
    count = int(publishable.get('count', 0) or 0)
    dashboard_exists = (RUNTIME / 'dashboard.html').exists()
    page_url = 'http://172.31.0.2:8510/dashboard.html'

    if status.get('ok') and count == 10 and dashboard_exists and len(items) >= 3:
        top3 = items[:3]
        lines = [
            '今日 AI 早报已生成',
            '',
            f'1. {top3[0].get("title", "")}',
            trim(str(top3[0].get('summary', '')), 60),
            '',
            f'2. {top3[1].get("title", "")}',
            trim(str(top3[1].get('summary', '')), 60),
            '',
            f'3. {top3[2].get("title", "")}',
            trim(str(top3[2].get('summary', '')), 60),
            '',
            f'完整页面：{page_url}',
        ]
    else:
        lines = [
            '今日 AI 早报生成失败',
            '',
            f'失败步骤：{status.get("step", "quality") or "quality"}',
            f'错误摘要：{status.get("error_summary", "未知错误") or "未知错误"}',
            f'当前页面：{"可访问旧版" if dashboard_exists else "页面不可用"}',
            '需要人工处理：请检查 collect / shortlist / draft / ranking / build_dashboard / quality 日志与产物。',
        ]

    RUNTIME.mkdir(parents=True, exist_ok=True)
    BRIEF.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    STATUS.write_text(json.dumps({**status, 'delivery_prepared_at': now_iso()}, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
