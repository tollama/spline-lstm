#!/usr/bin/env python3
"""CLI wrapper for edge benchmark harness.

Reports latency/size/stability and, when the export manifest contains
`edge_evaluation`, real holdout forecast accuracy for the exported runtime.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.training.edge_benchmark import main  # noqa: E402

if __name__ == "__main__":
    main()
