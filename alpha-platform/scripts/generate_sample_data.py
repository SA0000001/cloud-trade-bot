"""
Generate synthetic OHLCV CSV data for development and testing.

Usage:
    python scripts/generate_sample_data.py
    make generate-data
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.data.sample_data import generate_all_sample_csvs


def main() -> None:
    paths = generate_all_sample_csvs()
    print(f"Generated {len(paths)} sample CSV files.")
    for path in paths:
        print(path)


if __name__ == "__main__":
    main()
