"""Python wrapper around warehouse/ddl/apply.sh — same behaviour, callable
from inside a Dagster asset or unit test.

Usage:
    python scripts/init_warehouse.py
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DDL_DIR = REPO_ROOT / "warehouse" / "ddl"


def main() -> int:
    script = DDL_DIR / "apply.sh"
    if not script.exists():
        print(f"DDL script not found at {script}", file=sys.stderr)
        return 1
    proc = subprocess.run(
        ["bash", str(script)],
        env={**os.environ},
        check=False,
    )
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
