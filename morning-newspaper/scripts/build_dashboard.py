from __future__ import annotations

import argparse
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from morning_newspaper.dashboard import write_static_dashboard


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build static dashboard from top10_publishable.json")
    parser.add_argument("--runtime", default=str(PROJECT_ROOT / "runtime"))
    parser.add_argument("--output", default=str(PROJECT_ROOT / "runtime" / "dashboard.html"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    runtime_dir = Path(args.runtime)
    output_path = Path(args.output)
    result = write_static_dashboard(runtime_dir, output_path)
    print(f"wrote {result}")


if __name__ == "__main__":
    main()
