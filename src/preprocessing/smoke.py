"""Smoke entry for preprocessing pipeline.

Usage:
  python -m src.preprocessing.smoke --run-id smoke-001
  python -m src.preprocessing.smoke --input data/raw/sample.csv --run-id myrun
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from .pipeline import PreprocessingConfig, run_preprocessing_pipeline


def _make_synthetic_csv(path: Path, n: int = 180) -> None:
    t = pd.date_range("2025-01-01", periods=n, freq="h")
    y = np.sin(np.linspace(0, 18, n)) + 0.1 * np.random.randn(n)
    y[[10, 23, 77, 130]] = np.nan
    df = pd.DataFrame({"timestamp": t, "target": y})
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def main() -> None:
    p = argparse.ArgumentParser(description="Run preprocessing pipeline smoke test")
    p.add_argument("--input", type=str, default="", help="CSV/Parquet input path")
    p.add_argument("--run-id", type=str, required=True)
    p.add_argument("--lookback", type=int, default=24)
    p.add_argument("--horizon", type=int, default=1)
    p.add_argument("--scaling", type=str, default="standard", choices=["standard", "minmax"])
    p.add_argument("--artifacts-dir", type=str, default="artifacts")
    p.add_argument("--covariate-spec", type=str, default=None, help="Optional covariate schema JSON")
    p.add_argument("--knot-strategy", type=str, default="auto",
                   choices=["auto", "curvature", "uniform"],
                   help="Spline knot placement strategy")
    p.add_argument("--smoothing-method", type=str, default="legacy",
                   choices=["legacy", "pspline"],
                   help="Smoothing method: legacy (spline+savgol) or pspline")
    p.add_argument("--inject-spline-features", action="store_true", default=False,
                   help="Inject spline d1/d2/residual as LSTM covariates")
    p.add_argument("--residual-learning", action="store_true", default=False,
                   help="Enable residual learning (LSTM learns y - spline_trend)")
    args = p.parse_args()

    if args.input:
        input_path = Path(args.input)
    else:
        input_path = Path("data/raw/smoke_input.csv")
        _make_synthetic_csv(input_path)

    cfg = PreprocessingConfig(
        run_id=args.run_id,
        lookback=args.lookback,
        horizon=args.horizon,
        scaling=args.scaling,
        covariate_spec=args.covariate_spec,
        knot_strategy=args.knot_strategy,
        smoothing_method=args.smoothing_method,
        inject_spline_features=args.inject_spline_features,
        residual_mode=args.residual_learning,
    )

    paths = run_preprocessing_pipeline(
        input_path=str(input_path),
        config=cfg,
        artifacts_dir=args.artifacts_dir,
    )

    print("[OK] preprocessing smoke completed")
    for k, v in paths.items():
        print(f"- {k}: {v}")


if __name__ == "__main__":
    main()
