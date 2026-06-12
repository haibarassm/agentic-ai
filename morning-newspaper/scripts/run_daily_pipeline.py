from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str], *, cwd: Path) -> None:
    completed = subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True, check=False)
    if completed.stdout.strip():
        print(completed.stdout.strip())
    if completed.stderr.strip():
        print(completed.stderr.strip(), file=sys.stderr)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def main() -> None:
    parser = argparse.ArgumentParser(description='Run stable daily Morning-Newspaper-Assistant pipeline.')
    parser.add_argument('--python', default=sys.executable)
    parser.add_argument('--skip-tavily', action='store_true')
    parser.add_argument('--rebuild-dashboard-only', action='store_true')
    args = parser.parse_args()

    py = args.python
    root = PROJECT_ROOT

    if args.rebuild_dashboard_only:
        run([py, 'scripts/build_dashboard.py'], cwd=root)
        run([py, 'scripts/check_runtime_status.py'], cwd=root)
        return

    run([py, 'scripts/collect_mailbox.py'], cwd=root)

    collect_cmd = [py, 'scripts/collect_raw.py']
    if args.skip_tavily:
        collect_cmd.append('--skip-tavily')
    run(collect_cmd, cwd=root)
    run([py, 'scripts/enrich_content.py'], cwd=root)
    run([py, 'scripts/prepare_title_shortlist.py'], cwd=root)

    runtime = root / 'runtime'
    required = [
        runtime / 'title_shortlist_result.json',
        runtime / 'draft_result.json',
        runtime / 'top10_ranking_result.json',
    ]
    missing = [str(p.name) for p in required if not p.exists()]
    if missing:
        raise SystemExit('missing required result files: ' + ', '.join(missing))

    run([py, 'scripts/apply_title_shortlist.py'], cwd=root)
    run([py, 'scripts/prepare_draft_input.py'], cwd=root)
    run([py, 'scripts/apply_draft_results.py'], cwd=root)
    run([py, 'scripts/prepare_top10_ranking.py'], cwd=root)
    run([py, 'scripts/apply_top10_ranking.py'], cwd=root)
    run([py, 'scripts/build_dashboard.py'], cwd=root)
    run([py, 'scripts/check_runtime_status.py'], cwd=root)


if __name__ == '__main__':
    main()
