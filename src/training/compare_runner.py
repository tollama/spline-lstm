"""Phase 5 model comparison runner (LSTM vs GRU) for minimal PoC."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Dict

import numpy as np

from src.models.lstm import BACKEND, GRUModel, LSTMModel
from src.training.trainer import Trainer
from src.utils.repro import set_global_seed


def _make_run_id(prefix: str = "compare") -> str:
    return f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


def _generate_synthetic(n_samples: int = 800, noise: float = 0.08, seed: int = 42) -> np.ndarray:
    rng = np.random.default_rng(seed)
    t = np.linspace(0, 24 * np.pi, n_samples)
    y = np.sin(t) + 0.35 * np.sin(2.5 * t + 0.4) + noise * rng.normal(size=n_samples)
    return y.astype(np.float32)


def _run_single(model_name: str, series: np.ndarray, args: argparse.Namespace) -> Dict:
    model_cls = LSTMModel if model_name == "lstm" else GRUModel
    model = model_cls(
        sequence_length=args.sequence_length,
        hidden_units=args.hidden_units,
        dropout=args.dropout,
        learning_rate=args.learning_rate,
        output_units=args.horizon,
        input_features=1,
    )
    trainer = Trainer(
        model=model,
        sequence_length=args.sequence_length,
        prediction_horizon=args.horizon,
        save_dir=str(Path(args.artifacts_dir) / "checkpoints" / args.run_id / model_name),
    )
    result = trainer.train(
        data=series,
        epochs=args.epochs,
        batch_size=args.batch_size,
        test_size=args.test_size,
        val_size=args.val_size,
        normalize=args.normalize,
        normalize_method=args.normalize_method,
        early_stopping=args.early_stopping,
        verbose=args.verbose,
    )
    return {
        "metrics": result["metrics"],
        "split_indices": result.get("split_indices", {}),
    }


def run(args: argparse.Namespace) -> Dict:
    if BACKEND != "tensorflow":
        raise RuntimeError("TensorFlow backend is required for comparison runner.")

    args.run_id = args.run_id or _make_run_id()
    set_global_seed(args.seed)

    if args.input_npy:
        series = np.load(args.input_npy).astype(np.float32).reshape(-1)
    else:
        series = _generate_synthetic(args.synthetic_samples, args.synthetic_noise, seed=args.seed)

    comparisons = {
        "lstm": _run_single("lstm", series, args),
        "gru": _run_single("gru", series, args),
    }

    lstm_rmse = comparisons["lstm"]["metrics"]["rmse"]
    gru_rmse = comparisons["gru"]["metrics"]["rmse"]
    winner = "lstm" if lstm_rmse <= gru_rmse else "gru"

    payload = {
        "run_id": args.run_id,
        "backend": BACKEND,
        "config": {
            "sequence_length": args.sequence_length,
            "horizon": args.horizon,
            "hidden_units": args.hidden_units,
            "dropout": args.dropout,
            "learning_rate": args.learning_rate,
            "epochs": args.epochs,
            "batch_size": args.batch_size,
            "test_size": args.test_size,
            "val_size": args.val_size,
            "normalize": args.normalize,
            "normalize_method": args.normalize_method,
            "seed": args.seed,
        },
        "models": comparisons,
        "summary": {
            "winner_by_rmse": winner,
            "rmse_gap": float(abs(lstm_rmse - gru_rmse)),
        },
        "saved_at": datetime.now().isoformat(),
    }

    base = Path(args.artifacts_dir) / "comparisons"
    base.mkdir(parents=True, exist_ok=True)
    metrics_path = base / f"{args.run_id}.json"
    report_path = base / f"{args.run_id}.md"

    metrics_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    report = (
        "# Phase 5 Comparison Report\n\n"
        f"- run_id: `{args.run_id}`\n"
        f"- winner (RMSE): `{winner}`\n\n"
        "## RMSE\n"
        f"- LSTM: {lstm_rmse:.6f}\n"
        f"- GRU: {gru_rmse:.6f}\n"
        f"- Gap: {payload['summary']['rmse_gap']:.6f}\n\n"
        f"- metrics json: `{metrics_path}`\n"
    )
    report_path.write_text(report, encoding="utf-8")
    payload["artifacts"] = {"metrics": str(metrics_path), "report": str(report_path)}
    return payload


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Phase 5 model comparison (LSTM vs GRU)")
    p.add_argument("--run-id", type=str, default=None)
    p.add_argument("--artifacts-dir", type=str, default="artifacts")
    p.add_argument("--input-npy", type=str, default=None)
    p.add_argument("--synthetic-samples", type=int, default=800)
    p.add_argument("--synthetic-noise", type=float, default=0.08)
    p.add_argument("--sequence-length", type=int, default=24)
    p.add_argument("--horizon", type=int, default=1)
    p.add_argument("--hidden-units", type=int, nargs="+", default=[64, 32])
    p.add_argument("--dropout", type=float, default=0.2)
    p.add_argument("--learning-rate", type=float, default=1e-3)
    p.add_argument("--epochs", type=int, default=5)
    p.add_argument("--batch-size", type=int, default=32)
    p.add_argument("--test-size", type=float, default=0.2)
    p.add_argument("--val-size", type=float, default=0.2)
    p.add_argument("--normalize", action="store_true", default=True)
    p.add_argument("--no-normalize", action="store_false", dest="normalize")
    p.add_argument("--normalize-method", type=str, choices=["minmax", "standard"], default="minmax")
    p.add_argument("--early-stopping", action="store_true", default=True)
    p.add_argument("--no-early-stopping", action="store_false", dest="early_stopping")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--verbose", type=int, default=1)
    return p


def main() -> None:
    args = build_parser().parse_args()
    out = run(args)
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
