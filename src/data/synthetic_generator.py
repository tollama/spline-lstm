"""Synthetic time-series data generator for Spline-LSTM experiments.

Supports three scenarios:
- S1: smooth trend + seasonality (+ optional covariates)
- S2: structural break / regime shift
- S3: irregular spikes + heteroskedastic noise

Usage examples:
  python3 -m src.data.synthetic_generator --scenario S1 --seed 42
  python3 -m src.data.synthetic_generator --scenario S2 --covariates temp,promo,event
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Sequence

import numpy as np
import pandas as pd


@dataclass
class GeneratorConfig:
    scenario: str = "S1"
    n_samples: int = 720
    freq: str = "h"
    start: str = "2025-01-01"
    seed: int = 42
    noise_scale: float = 0.2
    covariates: Sequence[str] = ()
    out_dir: str = "data/raw/synthetic"
    file_stem: str | None = None


def _make_covariates(
    rng: np.random.Generator,
    t: np.ndarray,
    names: Sequence[str],
) -> dict[str, np.ndarray]:
    covs: dict[str, np.ndarray] = {}

    for name in names:
        key = name.strip()
        if not key:
            continue
        lower = key.lower()

        if lower in {"temp", "temperature"}:
            # smooth yearly-like and daily-like cycles
            covs[key] = 15 + 10 * np.sin(2 * np.pi * t / 24) + 3 * np.sin(2 * np.pi * t / (24 * 7))
        elif lower in {"promo", "event", "campaign"}:
            covs[key] = (rng.random(len(t)) < 0.08).astype(float)
        elif lower in {"dow", "dayofweek"}:
            covs[key] = (t // 24) % 7
        elif lower in {"hour", "hour_of_day"}:
            covs[key] = t % 24
        else:
            # generic exogenous signal
            covs[key] = 0.5 * np.sin(2 * np.pi * t / 48 + rng.uniform(0, np.pi)) + rng.normal(0, 0.3, len(t))

    return covs


def _scenario_s1(rng: np.random.Generator, t: np.ndarray, noise_scale: float) -> np.ndarray:
    trend = 0.01 * t
    seasonal_daily = 1.2 * np.sin(2 * np.pi * t / 24)
    seasonal_weekly = 0.7 * np.sin(2 * np.pi * t / (24 * 7))
    noise = rng.normal(0, noise_scale, len(t))
    return 10.0 + trend + seasonal_daily + seasonal_weekly + noise


def _scenario_s2(rng: np.random.Generator, t: np.ndarray, noise_scale: float) -> np.ndarray:
    y = _scenario_s1(rng, t, noise_scale=noise_scale * 0.9)
    break_idx = int(len(t) * 0.55)

    # structural level shift + slope increase after break
    post = np.maximum(0, t - break_idx)
    y += (t >= break_idx).astype(float) * 2.5
    y += 0.015 * post

    # temporary shock window
    shock_start = min(len(t) - 1, int(len(t) * 0.7))
    shock_end = min(len(t), shock_start + max(6, len(t) // 40))
    y[shock_start:shock_end] -= 2.0
    return y


def _scenario_s3(rng: np.random.Generator, t: np.ndarray, noise_scale: float) -> np.ndarray:
    baseline = 8.0 + 0.006 * t + 0.9 * np.sin(2 * np.pi * t / 24)

    # heteroskedastic noise (variance grows slowly over time)
    sigma = noise_scale * (0.8 + 0.003 * t)
    noise = rng.normal(0, sigma, len(t))
    y = baseline + noise

    # sparse positive/negative spikes
    spike_mask = rng.random(len(t)) < 0.025
    spike_amp = rng.normal(loc=0.0, scale=3.5, size=len(t))
    y += spike_mask * spike_amp
    return y


def generate_dataframe(config: GeneratorConfig) -> pd.DataFrame:
    rng = np.random.default_rng(config.seed)
    t = np.arange(config.n_samples)
    timestamps = pd.date_range(config.start, periods=config.n_samples, freq=config.freq)

    scenario_map: dict[str, Callable[[np.random.Generator, np.ndarray, float], np.ndarray]] = {
        "S1": _scenario_s1,
        "S2": _scenario_s2,
        "S3": _scenario_s3,
    }
    scenario = config.scenario.upper()
    if scenario not in scenario_map:
        raise ValueError(f"Unsupported scenario '{config.scenario}'. Choose one of: S1, S2, S3")

    target = scenario_map[scenario](rng, t, config.noise_scale)
    covs = _make_covariates(rng, t, config.covariates)

    df = pd.DataFrame({"timestamp": timestamps, "target": target})
    for col, values in covs.items():
        # tiny scenario-linked influence to make covariates realistic
        if col.lower() in {"promo", "event", "campaign"}:
            df["target"] += 0.6 * values
        if col.lower() in {"temp", "temperature"}:
            df["target"] += 0.05 * (values - np.mean(values))
        df[col] = values

    return df


def save_outputs(df: pd.DataFrame, config: GeneratorConfig) -> tuple[Path, Path]:
    out_dir = Path(config.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    scenario = config.scenario.upper()
    stem = config.file_stem or f"synthetic_{scenario}_n{config.n_samples}_seed{config.seed}"
    csv_path = out_dir / f"{stem}.csv"
    meta_path = out_dir / f"{stem}.meta.json"

    df.to_csv(csv_path, index=False)

    metadata = {
        "generator": "src.data.synthetic_generator",
        "config": {
            **asdict(config),
            "covariates": list(config.covariates),
        },
        "outputs": {
            "csv": str(csv_path),
            "meta": str(meta_path),
        },
        "stats": {
            "rows": int(len(df)),
            "columns": list(df.columns),
            "target_mean": float(df["target"].mean()),
            "target_std": float(df["target"].std(ddof=0)),
            "target_min": float(df["target"].min()),
            "target_max": float(df["target"].max()),
            "timestamp_start": str(df["timestamp"].iloc[0]),
            "timestamp_end": str(df["timestamp"].iloc[-1]),
        },
    }

    meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return csv_path, meta_path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate synthetic time-series CSV + metadata JSON")
    p.add_argument("--scenario", type=str, default="S1", choices=["S1", "S2", "S3"], help="Synthetic scenario")
    p.add_argument("--n-samples", type=int, default=720, help="Number of rows")
    p.add_argument("--freq", type=str, default="h", help="Pandas frequency string (default: h)")
    p.add_argument("--start", type=str, default="2025-01-01", help="Start timestamp")
    p.add_argument("--seed", type=int, default=42, help="Random seed")
    p.add_argument("--noise-scale", type=float, default=0.2, help="Base noise scale")
    p.add_argument(
        "--covariates",
        type=str,
        default="",
        help="Comma-separated covariate columns, e.g. temp,promo,event",
    )
    p.add_argument("--out-dir", type=str, default="data/raw/synthetic", help="Output directory")
    p.add_argument("--file-stem", type=str, default="", help="Optional output file stem")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    covariates = tuple(c.strip() for c in args.covariates.split(",") if c.strip())
    cfg = GeneratorConfig(
        scenario=args.scenario,
        n_samples=args.n_samples,
        freq=args.freq,
        start=args.start,
        seed=args.seed,
        noise_scale=args.noise_scale,
        covariates=covariates,
        out_dir=args.out_dir,
        file_stem=args.file_stem or None,
    )

    df = generate_dataframe(cfg)
    csv_path, meta_path = save_outputs(df, cfg)

    print("[OK] synthetic data generated")
    print(f"- scenario: {cfg.scenario}")
    print(f"- rows: {len(df)}")
    print(f"- columns: {', '.join(df.columns)}")
    print(f"- csv: {csv_path}")
    print(f"- meta: {meta_path}")


if __name__ == "__main__":
    main()
