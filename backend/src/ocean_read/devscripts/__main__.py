"""Run repo ``scripts/empty_dev_*.sh`` from any cwd (requires Docker + Compose).

Examples (from ``backend/`` with the package on ``PYTHONPATH``, e.g. editable install)::

    python -m ocean_read.devscripts database
    python -m ocean_read.devscripts testing
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    # .../backend/src/ocean_read/devscripts/__main__.py -> repo root
    return Path(__file__).resolve().parents[4]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Empty dev data: wraps scripts/empty_dev_database.sh and scripts/empty_dev_testing.sh.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("database", help="Delete all projects (CASCADE); ensure default organization.")
    sub.add_parser("testing", help="Database wipe + clear backend /data/uploads volume contents.")
    args = parser.parse_args()
    root = _repo_root()
    name = "empty_dev_database.sh" if args.cmd == "database" else "empty_dev_testing.sh"
    script = root / "scripts" / name
    if not script.is_file():
        print(f"Expected script at {script}", file=sys.stderr)
        return 2
    proc = subprocess.run(["bash", str(script)], cwd=root, check=False)
    return int(proc.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
