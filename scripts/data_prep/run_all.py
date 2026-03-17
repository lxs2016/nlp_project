#!/usr/bin/env python3
"""Run full data preparation pipeline in order (00 -> 01 -> 02 -> 03 -> 04)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    script_dir = Path(__file__).resolve().parent
    steps = [
        "00_fetch_raw.py",
        "01_clean.py",
        "02_segment_plot_units.py",
        "03_build_intent_annotations.py",
        "04_build_consistency_annotations.py",
    ]
    for name in steps:
        path = script_dir / name
        print(f"\n--- {name} ---")
        ret = subprocess.run([sys.executable, str(path)], cwd=script_dir.parents[1])
        if ret.returncode != 0:
            return ret.returncode
    print("\nData preparation complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
