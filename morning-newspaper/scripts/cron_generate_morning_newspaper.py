from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNTIME = PROJECT_ROOT / 'runtime'
STATUS = RUNTIME / 'cron_status.json'

STEP_HINTS = [
    ('collect', ['collected_raw.json', 'collect_raw.py', 'collect_mailbox.py', 'missing IMAP_USER', 'tavily']),
    ('shortlist', ['title_shortlist_result.json', 'shortlist.json', 'prepare_title_shortlist.py', 'apply_title_shortlist.py']),
    ('draft', ['draft_result.json', 'drafted_items.json', 'prepare_draft_input.py', 'apply_draft_results.py']),
    ('ranking', ['top10_ranking_result.json', 'top10_publishable.json', 'prepare_top10_ranking.py', 'apply_top10_ranking.py']),
    ('build_dashboard', ['dashboard.html', 'build_dashboard.py']),
    ('quality', ['check_runtime_status.py', 'runtime check failed', 'top10_count=', 'summary_placeholders']),
]


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def write_status(payload: dict) -> None:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    STATUS.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def detect_step(stdout: str, stderr: str, returncode: int) -> str:
    text = '\n'.join([stdout or '', stderr or ''])
    lower_text = text.lower()

    stale_markers = [
        'title_shortlist_result.json stale or mismatched',
        'draft_result.json stale or mismatched',
        'top10_ranking_result.json stale or mismatched',
    ]
    if any(marker in text for marker in stale_markers):
        if 'title_shortlist_result.json stale or mismatched' in text:
            return 'shortlist'
        if 'draft_result.json stale or mismatched' in text:
            return 'draft'
        if 'top10_ranking_result.json stale or mismatched' in text:
            return 'ranking'

    if 'runtime check failed' in lower_text:
        return 'quality'

    for step, hints in STEP_HINTS:
        if any(h.lower() in lower_text for h in hints):
            return step
    if returncode != 0:
        return 'quality'
    return 'done'


def main() -> int:
    cmd = [sys.executable, 'scripts/run_daily_pipeline.py']
    completed = subprocess.run(cmd, cwd=str(PROJECT_ROOT), text=True, capture_output=True)

    stdout = completed.stdout.strip()
    stderr = completed.stderr.strip()

    top10_count = 0
    dashboard_exists = (RUNTIME / 'dashboard.html').exists()
    publishable = RUNTIME / 'top10_publishable.json'
    if publishable.exists():
        try:
            top10_count = int(json.loads(publishable.read_text(encoding='utf-8')).get('count', 0) or 0)
        except Exception:
            top10_count = 0

    ok = completed.returncode == 0 and top10_count > 0 and dashboard_exists
    step = detect_step(stdout, stderr, completed.returncode)
    payload = {
        'generated_at': now_iso(),
        'ok': ok,
        'returncode': completed.returncode,
        'step': step,
        'top10_count': top10_count,
        'dashboard_exists': dashboard_exists,
        'stdout_tail': '\n'.join(stdout.splitlines()[-40:]) if stdout else '',
        'stderr_tail': '\n'.join(stderr.splitlines()[-40:]) if stderr else '',
        'error_summary': stderr.splitlines()[-1] if stderr else (stdout.splitlines()[-1] if stdout else ''),
    }
    write_status(payload)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
