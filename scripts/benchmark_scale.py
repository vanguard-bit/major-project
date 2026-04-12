"""Print Analysis Engine scalability table (stdout). Run: python scripts/benchmark_scale.py"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ait.scale_bench import tabulate_rows  # noqa: E402


def main() -> None:
    print("Allowlisted endpoints | Mean analyze time (ms) | Findings | Risk")
    print("----------------------|----------------------|----------|-----")
    for n, ms, findings, risk in tabulate_rows():
        print(f"{n:>21} | {ms:>20} | {findings:>8} | {risk:>3}")


if __name__ == "__main__":
    main()
