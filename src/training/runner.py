"""CLI runner for train -> eval -> infer in a single command (MVP Phase 3/5)."""

from __future__ import annotations

import argparse
import csv
import json
import logging
import pickle
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import numpy as np

from src.covariates.spec import enforce_covariate_spec, load_covariate_spec
from src.models.lstm import BACKEND, GRUModel, LSTMModel
from src.training.baselines import Phase3BaselineComparisonError, build_baseline_report
from src.training.trainer import Trainer
from src.utils.repro import build_phase3_run_metadata, build_run_metadata, get_git_commit_info, set_global_seed
from src.utils.run_id import validate_run_id

logger = logging.getLogger(__name__)


def _fail_contract(code: str, message: str) -> ValueError:
    return ValueError(f"[{code}] {message}")


class Phase3BaselineComparisonSkippedError(ValueError):
    """Raised when a required Phase 3 baseline comparison was skipped."""


class Phase3MetadataContractError(ValueError):
    """Raised when Phase 3 run metadata contract validation fails."""


def _make_run_id(prefix: str = "run") -> str:
    git_info = get_git_commit_info(repo_dir=".")
    commit_hash = git_info.get("commit_hash")
    commit = commit_hash[:7].lower() if isinstance(commit_hash, str) and commit_hash else "nogit000"
    return f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{commit}"


def _generate_synthetic(n_samples: int = 800, noise: float = 0.08, seed: int = 42) -> np.ndarray:
    rng = np.random.default_rng(seed)
    t = np.linspace(0, 24 * np.pi, n_samples)
    y = np.sin(t) + 0.35 * np.sin(2.5 * t + 0.4) + noise * rng.normal(size=n_samples)
    return np.asarray(y, dtype=np.float32)


def _parse_csv_like(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [x.strip() for x in raw.split(",") if x.strip()]


def _parse_export_formats(raw: str | None) -> list[str]:
    """Parse and validate export format contract.

    Allowed values: none | onnx | tflite | onnx,tflite
    """
    formats = _parse_csv_like(raw)
    if not formats:
        return ["none"]

    allowed = {"none", "onnx", "tflite"}
    invalid = [x for x in formats if x not in allowed]
    if invalid:
        raise ValueError(f"unsupported export format(s): {invalid}; allowed={sorted(allowed)}")

    if "none" in formats and len(formats) > 1:
        raise ValueError("'none' cannot be combined with other export formats")

    # deterministic dedupe while preserving order
    deduped: list[str] = []
    for x in formats:
        if x not in deduped:
            deduped.append(x)
    return deduped


def _validate_processed_contract_keys(payload: Any) -> None:
    missing = [k for k in ("feature_names", "target_indices") if k not in payload]
    if missing:
        raise _fail_contract("ARTIFACT_CONTRACT_ERROR", f"processed.npz missing required keys: {missing}")


def _validate_split_contract_if_applicable(processed_npz: str) -> None:
    path = Path(processed_npz)
    if path.name != "processed.npz":
        return

    parts = path.parts
    if "processed" not in parts:
        return
    idx = parts.index("processed")
    if idx + 1 >= len(parts):
        return

    split_contract_path = path.parent / "split_contract.json"
    if not split_contract_path.exists():
        raise _fail_contract(
            "ARTIFACT_CONTRACT_ERROR",
            f"split_contract.json not found next to processed.npz: {split_contract_path}",
        )

    with open(split_contract_path, encoding="utf-8") as f:
        contract = json.load(f)
    schema_version = contract.get("schema_version")
    if schema_version != "phase1.split_contract.v1":
        raise _fail_contract(
            "ARTIFACT_CONTRACT_ERROR",
            f"split_contract.json schema_version mismatch: expected phase1.split_contract.v1, got {schema_version}",
        )


def _load_series(args: argparse.Namespace) -> np.ndarray:
    if args.processed_npz:
        payload = np.load(args.processed_npz)
        _validate_processed_contract_keys(payload)
        _validate_split_contract_if_applicable(args.processed_npz)
        if "scaled" in payload:
            return np.asarray(payload["scaled"], dtype=np.float32)
        if "raw_target" in payload:
            return np.asarray(payload["raw_target"], dtype=np.float32)
        raise _fail_contract("ARTIFACT_CONTRACT_ERROR", "processed.npz must contain one of: scaled, raw_target")

    if args.input_npy:
        arr = np.load(args.input_npy)
        return np.asarray(arr, dtype=np.float32).reshape(-1)

    return _generate_synthetic(n_samples=args.synthetic_samples, noise=args.synthetic_noise, seed=args.seed)


def _load_training_arrays(args: argparse.Namespace) -> tuple[Any | None, np.ndarray | None]:
    """Load pre-windowed X/y when available for Phase 5 contract.
    Returns:
        X: List of [X_past, X_future, X_static] or a single numpy array
        y: target array
    """
    if not args.processed_npz:
        return None, None

    payload = np.load(args.processed_npz)
    _validate_processed_contract_keys(payload)
    _validate_split_contract_if_applicable(args.processed_npz)

    x_past = payload.get("X", payload.get("X_mv", None))
    y = payload.get("y", payload.get("y_mv", None))

    if x_past is None or y is None:
        return None, None

    x_past = np.asarray(x_past, dtype=np.float32)
    y = np.asarray(y, dtype=np.float32)

    # Check for future and static
    x_fut = payload.get("X_fut")
    x_stat = payload.get("static_features")

    if (x_fut is not None and x_fut.size > 0) or (x_stat is not None and x_stat.size > 0):
        X = [x_past]
        if x_fut is not None and x_fut.size > 0:
            X.append(np.asarray(x_fut, dtype=np.float32))
        else:
            X.append(None)

        if x_stat is not None and x_stat.size > 0:
            X.append(np.asarray(x_stat, dtype=np.float32))
        else:
            X.append(None)
    else:
        X = x_past

    return X, y


def _load_processed_feature_names(processed_npz: str | None) -> list[str]:
    if not processed_npz:
        return []
    payload = np.load(processed_npz)
    if "feature_names" not in payload:
        return []
    names = [str(x) for x in np.asarray(payload["feature_names"]).reshape(-1)]
    return [x for x in names if x]


def _extract_run_id_from_processed_path(processed_npz: str) -> str | None:
    path = Path(processed_npz)
    # expected: .../processed/{run_id}/processed.npz
    if path.name != "processed.npz":
        return None
    parts = path.parts
    if "processed" not in parts:
        return None
    idx = parts.index("processed")
    if idx + 1 >= len(parts):
        return None
    return parts[idx + 1]


def _load_preprocessor_run_id(preprocessor_path: Path) -> str | None:
    if not preprocessor_path.exists():
        return None
    with open(preprocessor_path, "rb") as f:
        payload = pickle.load(f)
    if isinstance(payload, dict):
        rid = payload.get("run_id")
        if isinstance(rid, str) and rid.strip():
            return rid
    return None


def _validate_run_id_consistency(run_id: str, args: argparse.Namespace) -> Path | None:
    if not args.processed_npz:
        return None

    processed_path = Path(args.processed_npz)
    processed_run_id = _extract_run_id_from_processed_path(args.processed_npz)
    if processed_run_id and processed_run_id != run_id:
        raise ValueError(f"run_id mismatch: cli run_id={run_id} but processed artifact path run_id={processed_run_id}")

    meta_path = processed_path.parent / "meta.json"
    if meta_path.exists():
        with open(meta_path, encoding="utf-8") as f:
            meta = json.load(f)
        meta_run_id = meta.get("run_id")
        if isinstance(meta_run_id, str) and meta_run_id != run_id:
            raise ValueError(f"run_id mismatch: cli run_id={run_id} but meta.json run_id={meta_run_id}")

    if args.preprocessor_pkl:
        preprocessor_path = Path(args.preprocessor_pkl)
    elif processed_run_id:
        # infer: <artifacts>/processed/{run_id}/processed.npz -> <artifacts>/models/{run_id}/preprocessor.pkl
        preprocessor_path = processed_path.parents[2] / "models" / processed_run_id / "preprocessor.pkl"
    else:
        preprocessor_path = None

    if preprocessor_path is None:
        return None

    preprocessor_run_id = _load_preprocessor_run_id(preprocessor_path)
    if preprocessor_run_id and preprocessor_run_id != run_id:
        raise ValueError(
            f"run_id mismatch: model/training run_id ({run_id}) != preprocessor run_id ({preprocessor_run_id})"
        )

    return preprocessor_path if preprocessor_path.exists() else None


def _write_json(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def _write_report(path: Path, report: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report, encoding="utf-8")


def _write_predictions_csv(path: Path, run_id: str, y_pred_last: np.ndarray) -> None:
    """Write inference prediction contract rows for the latest window."""
    path.parent.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now().isoformat()
    values = np.asarray(y_pred_last, dtype=np.float32).reshape(-1)

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["run_id", "horizon_step", "y_pred", "generated_at"])
        writer.writeheader()
        for i, v in enumerate(values, start=1):
            writer.writerow(
                {
                    "run_id": run_id,
                    "horizon_step": i,
                    "y_pred": float(v),
                    "generated_at": generated_at,
                }
            )


def _map_exception_to_exit_code(exc: Exception) -> int:
    """Map known contract failures to stable CLI exit codes.

    Phase 3 dedicated mapping:
    - 32: invalid baseline comparison contract (hard-fail)
    - 33: explicit comparison-skipped violation
    - 34: explicit Phase 3 metadata contract violation
    """
    if isinstance(exc, FileNotFoundError):
        return 21
    if isinstance(exc, Phase3BaselineComparisonError):
        return 32
    if isinstance(exc, Phase3BaselineComparisonSkippedError):
        return 33
    if isinstance(exc, Phase3MetadataContractError):
        return 34

    msg = str(exc).lower()
    if "run_id mismatch" in msg:
        return 27
    if "phase3 baseline comparison skipped" in msg:
        return 33
    if "phase3 metadata contract invalid" in msg:
        return 34
    if any(token in msg for token in ["must be 3d", "must be 2d", "lookback mismatch", "shape", "batch size mismatch"]):
        return 23
    if any(token in msg for token in ["input length", "insufficient data"]):
        return 26
    if any(
        token in msg
        for token in [
            "artifact_contract_error",
            "processed.npz",
            "must contain one of",
            "invalid artifact path layout",
            "split_contract.json",
            "feature_names",
            "target_indices",
        ]
    ):
        return 22
    return 24


def _build_error_payload(exc: Exception) -> dict[str, Any]:
    code = _map_exception_to_exit_code(exc)
    msg = str(exc)
    msg_lower = msg.lower()

    if code == 21:
        error_code = "FILE_NOT_FOUND"
    elif code == 22:
        error_code = "ARTIFACT_CONTRACT_ERROR"
    elif code == 23:
        error_code = "INPUT_SHAPE_ERROR"
    elif code == 26:
        error_code = "INSUFFICIENT_DATA_ERROR"
    elif code == 27:
        error_code = "RUN_ID_MISMATCH"
    elif code == 32:
        error_code = "PHASE3_BASELINE_COMPARISON_INVALID"
    elif code == 33:
        error_code = "PHASE3_BASELINE_COMPARISON_SKIPPED"
    elif code == 34:
        error_code = "PHASE3_METADATA_CONTRACT_INVALID"
    elif "tensorflow backend is required" in msg_lower:
        error_code = "BACKEND_REQUIRED"
    else:
        error_code = "RUNNER_EXEC_ERROR"

    return {
        "ok": False,
        "exit_code": code,
        "error": {
            "code": error_code,
            "message": msg,
            "type": exc.__class__.__name__,
        },
    }


def _validate_phase3_metadata_contract(run_id: str, runmeta: dict[str, Any]) -> None:
    """Validate strict Phase 3 runmeta contract before persisting artifacts."""

    def _require(condition: bool, message: str) -> None:
        if not condition:
            raise Phase3MetadataContractError(f"phase3 metadata contract invalid: {message}")

    def _require_dict(obj: Any, path: str) -> dict[str, Any]:
        _require(isinstance(obj, dict), f"'{path}' must be object")
        return cast(dict[str, Any], obj)

    def _require_str(obj: Any, path: str) -> str:
        _require(isinstance(obj, str) and bool(obj.strip()), f"'{path}' must be non-empty string")
        return cast(str, obj)

    def _require_bool(obj: Any, path: str) -> bool:
        _require(isinstance(obj, bool), f"'{path}' must be boolean")
        return cast(bool, obj)

    def _require_int(obj: Any, path: str) -> int:
        _require(isinstance(obj, int) and not isinstance(obj, bool), f"'{path}' must be integer")
        return cast(int, obj)

    _require_dict(runmeta, "$")
    _require(runmeta.get("schema_version") == "phase3.runmeta.v1", "'schema_version' must be 'phase3.runmeta.v1'")
    _require(runmeta.get("run_id") == run_id, f"'run_id' must equal cli run_id='{run_id}'")

    _require_str(runmeta.get("created_at"), "created_at")
    _require_str(runmeta.get("project"), "project")
    _require(runmeta.get("project") == "spline-lstm", "'project' must be 'spline-lstm'")

    git = _require_dict(runmeta.get("git"), "git")
    _require("commit" in git, "'git.commit' key is required (value may be null)")
    if git.get("commit") is not None:
        _require_str(git.get("commit"), "git.commit")
    _require_str(git.get("source"), "git.source")

    runtime = _require_dict(runmeta.get("runtime"), "runtime")
    _require_str(runtime.get("python"), "runtime.python")
    _require_str(runtime.get("platform"), "runtime.platform")
    _require_str(runtime.get("backend"), "runtime.backend")

    repro = _require_dict(runmeta.get("reproducibility"), "reproducibility")
    seed = _require_dict(repro.get("seed"), "reproducibility.seed")
    _require_int(seed.get("python"), "reproducibility.seed.python")
    _require_int(seed.get("numpy"), "reproducibility.seed.numpy")
    _require_int(seed.get("tensorflow"), "reproducibility.seed.tensorflow")

    deterministic = _require_dict(repro.get("deterministic"), "reproducibility.deterministic")
    _require_bool(deterministic.get("enabled"), "reproducibility.deterministic.enabled")
    _require_bool(deterministic.get("tf_deterministic_ops"), "reproducibility.deterministic.tf_deterministic_ops")
    _require_bool(deterministic.get("shuffle"), "reproducibility.deterministic.shuffle")

    split = _require_dict(repro.get("split_index"), "reproducibility.split_index")
    raw = _require_dict(split.get("raw"), "reproducibility.split_index.raw")
    seq = _require_dict(split.get("sequence"), "reproducibility.split_index.sequence")

    _require_int(raw.get("n_total"), "reproducibility.split_index.raw.n_total")
    _require_int(raw.get("train_end"), "reproducibility.split_index.raw.train_end")
    _require_int(raw.get("val_end"), "reproducibility.split_index.raw.val_end")
    _require_int(raw.get("test_start"), "reproducibility.split_index.raw.test_start")

    _require_int(seq.get("n_train_seq"), "reproducibility.split_index.sequence.n_train_seq")
    _require_int(seq.get("n_val_seq"), "reproducibility.split_index.sequence.n_val_seq")
    _require_int(seq.get("n_test_seq"), "reproducibility.split_index.sequence.n_test_seq")
    _require_int(seq.get("lookback"), "reproducibility.split_index.sequence.lookback")
    _require_int(seq.get("horizon"), "reproducibility.split_index.sequence.horizon")

    _require_dict(runmeta.get("config"), "config")
    _require_dict(runmeta.get("artifacts"), "artifacts")


def _build_callbacks(checkpoint_dir: Path):
    # Keep callback wiring lightweight for compatibility with older TF/Keras builds.
    # Runtime checkpointing in `run()` handles artifact persistence explicitly.
    return []


def _build_model(
    args: argparse.Namespace, output_units: int, input_features: int, static_features: int = 0, future_features: int = 0
):
    model_map = {
        "lstm": LSTMModel,
        "gru": GRUModel,
    }
    model_cls = model_map.get(args.model_type, LSTMModel)

    return model_cls(
        sequence_length=args.sequence_length,
        hidden_units=args.hidden_units,
        dropout=args.dropout,
        learning_rate=args.learning_rate,
        output_units=output_units,
        input_features=input_features,
        static_features=static_features,
        future_features=future_features,
    )


def _compute_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    mae = np.mean(np.abs(y_true - y_pred))
    mse = np.mean((y_true - y_pred) ** 2)
    rmse = np.sqrt(mse)

    mask = y_true != 0
    mape = np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100 if mask.sum() > 0 else np.inf

    epsilon = 1e-8
    denom = np.maximum(np.abs(y_true), epsilon)
    mape_zero_safe = np.mean(np.abs((y_true - y_pred) / denom)) * 100

    if y_true.shape[0] > 1:
        naive_diff = np.abs(y_true[1:, 0] - y_true[:-1, 0]) if y_true.ndim == 2 else np.abs(y_true[1:] - y_true[:-1])
        naive_mae = np.mean(naive_diff)
    else:
        naive_mae = np.inf
    mase = mae / naive_mae if naive_mae > 0 else np.inf

    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    r2 = 1 - (ss_res / (ss_tot + 1e-8))

    return {
        "mae": float(mae),
        "mse": float(mse),
        "rmse": float(rmse),
        "mape": float(mape),
        "mase": float(mase),
        "r2": float(r2),
        "mape_zero_safe": float(mape_zero_safe),
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    if BACKEND != "tensorflow":
        raise RuntimeError("TensorFlow backend is required for Phase 3 runner. Install tensorflow and retry.")

    run_id = args.run_id or _make_run_id()
    run_id = validate_run_id(run_id, mode=args.run_id_validation)
    preprocessor_path = _validate_run_id_consistency(run_id, args)
    seed_info = set_global_seed(args.seed, deterministic=args.deterministic)

    target_cols = _parse_csv_like(args.target_cols)
    dynamic_covariates = _parse_csv_like(args.dynamic_covariates)
    static_covariates = _parse_csv_like(args.static_covariates)
    covariate_spec_raw = load_covariate_spec(args.covariate_spec)
    covariate_contract = enforce_covariate_spec(
        declared_dynamic=dynamic_covariates,
        declared_static=static_covariates,
        available_columns=_load_processed_feature_names(args.processed_npz),
        spec_payload=covariate_spec_raw,
        context="runner",
    )
    dynamic_covariates = covariate_contract["dynamic_covariates"]
    static_covariates = covariate_contract["static_covariates"]
    covariate_spec = covariate_contract["spec"]
    export_formats = _parse_export_formats(args.export_formats)

    base = Path(args.artifacts_dir)
    checkpoint_base = Path(args.checkpoints_dir) if args.checkpoints_dir else (base / "checkpoints")
    checkpoint_dir = checkpoint_base / run_id
    metrics_path = base / "metrics" / f"{run_id}.json"
    report_path = base / "reports" / f"{run_id}.md"
    baseline_path = base / "baselines" / f"{run_id}.json"
    split_path = base / "splits" / f"{run_id}.json"
    predictions_path = base / "predictions" / f"{run_id}.csv"
    config_snapshot_path = base / "configs" / f"{run_id}.json"
    metadata_path = base / "metadata" / f"{run_id}.json"
    runmeta_path = base / "runs" / f"{run_id}.meta.json"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)

    callbacks = _build_callbacks(checkpoint_dir)

    X_direct, y_direct = _load_training_arrays(args)
    split_indices: dict[str, Any] = {}
    baselines_obj: dict[str, Any] = {
        "skipped": True,
        "reason": "only computed for univariate series mode",
    }

    if X_direct is not None and y_direct is not None:
        # Contract path: use pre-windowed arrays directly.
        if isinstance(X_direct, list):
            x_main = X_direct[0]
            input_features = int(x_main.shape[2])
            future_features = int(X_direct[1].shape[2]) if X_direct[1] is not None else 0
            static_features = int(X_direct[2].shape[1]) if X_direct[2] is not None else 0
        else:
            input_features = int(X_direct.shape[2])
            future_features = 0
            static_features = 0

        output_units = int(y_direct.shape[1])
        model = _build_model(
            args,
            output_units=output_units,
            input_features=input_features,
            static_features=static_features,
            future_features=future_features,
        )

        trainer = Trainer(
            model=model,
            sequence_length=args.sequence_length,
            prediction_horizon=args.horizon,
            save_dir=str(checkpoint_dir),
        )

        if args.cv_splits > 0:
            logger.info(f"Running {args.cv_splits}-fold cross-validation...")
            cv_results = trainer.cross_validate(
                X=X_direct,
                y=y_direct,
                n_splits=args.cv_splits,
                epochs=args.epochs,
                batch_size=args.batch_size,
                verbose=args.verbose,
            )
            # Use CV metrics as primary results context if needed
            logger.info(f"CV Avg RMSE: {cv_results['avg_metrics']['rmse']:.4f}")

        results = trainer.train(
            X=X_direct,
            y=y_direct,
            epochs=args.epochs,
            batch_size=args.batch_size,
            test_size=args.test_size,
            val_size=args.val_size,
            verbose=args.verbose,
            extra_callbacks=callbacks,
        )
        split_indices = results.get("split_indices", {})
        y_pred = results["y_pred"]
        y_test = results["y_test"]
        X_test = results["X_test"]

        # Only compute simple baselines for classic univariate contract.
        if args.feature_mode == "univariate":
            if y_test.shape[1] != args.horizon:
                raise Phase3BaselineComparisonError(
                    "phase3 baseline comparison invalid: univariate mode requires y.shape[1] == horizon"
                )
            baselines_obj = build_baseline_report(
                y_true=y_test,
                y_lstm=y_pred,
                X_test=X_test,
                horizon=args.horizon,
                ma_window=args.ma_window,
            )
    else:
        series = _load_series(args)
        inferred_features = 1 if series.ndim == 1 else int(series.shape[1])
        f_target = max(1, len(target_cols))
        output_units = args.horizon if args.feature_mode == "univariate" else args.horizon * f_target

        model = _build_model(args, output_units=output_units, input_features=inferred_features)
        trainer = Trainer(
            model=model,
            sequence_length=args.sequence_length,
            prediction_horizon=args.horizon,
            save_dir=str(checkpoint_dir),
        )

        results = trainer.train(
            data=series,
            epochs=args.epochs,
            batch_size=args.batch_size,
            test_size=args.test_size,
            val_size=args.val_size,
            normalize=args.normalize,
            normalize_method=args.normalize_method,
            early_stopping=args.early_stopping,
            verbose=args.verbose,
            extra_callbacks=callbacks,
        )
        split_indices = results.get("split_indices", {})

        baselines_obj = build_baseline_report(
            y_true=trainer.y_test,
            y_lstm=trainer.y_pred,
            X_test=trainer.X_test,
            horizon=args.horizon,
            ma_window=args.ma_window,
        )

        X_test, y_test, y_pred = trainer.X_test, trainer.y_test, trainer.y_pred

    last_ckpt = checkpoint_dir / "last.keras"
    last_ckpt_h5 = checkpoint_dir / "last.h5"
    model.save(str(last_ckpt_h5))
    if not last_ckpt.exists():
        shutil.copy2(last_ckpt_h5, last_ckpt)

    best_ckpt = checkpoint_dir / "best.keras"
    best_ckpt_h5 = checkpoint_dir / "best.h5"
    if not best_ckpt.exists() and not best_ckpt_h5.exists():
        model.save(str(best_ckpt_h5))
        shutil.copy2(best_ckpt_h5, best_ckpt)

    x_last = X_test[-1:]
    y_true_last = y_test[-1]
    y_pred_last = y_pred[-1]
    _write_predictions_csv(predictions_path, run_id=run_id, y_pred_last=y_pred_last)

    if "evaluation_context" not in baselines_obj:
        baselines_obj["evaluation_context"] = {
            "split": "test",
            "scale": "train_fit_only_then_transform",
            "horizon": int(args.horizon),
            "sequence_length": int(args.sequence_length),
        }

    config_snapshot: dict[str, Any] = {
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
        "deterministic": args.deterministic,
        "ma_window": args.ma_window,
        "processed_npz": args.processed_npz,
        "preprocessor_pkl": str(preprocessor_path) if preprocessor_path else args.preprocessor_pkl,
        "input_npy": args.input_npy,
        "synthetic_samples": args.synthetic_samples,
        "synthetic_noise": args.synthetic_noise,
        "model_type": args.model_type,
        "feature_mode": args.feature_mode,
        "target_cols": target_cols,
        "dynamic_covariates": dynamic_covariates,
        "static_covariates": static_covariates,
        "covariate_spec": covariate_spec,
        "covariate_contract": covariate_contract,
        "export_formats": export_formats,
    }
    run_metadata = build_run_metadata(run_id=run_id, seed_info=seed_info, config=config_snapshot, repo_dir=".")
    runmeta_v1 = build_phase3_run_metadata(
        run_id=run_id,
        seed=args.seed,
        deterministic=args.deterministic,
        split_indices=split_indices,
        config=config_snapshot,
        artifacts={
            "best_checkpoint": str(best_ckpt),
            "last_checkpoint": str(last_ckpt),
            "metrics": str(metrics_path),
            "report": str(report_path),
        },
        status="success",
        repo_dir=".",
    )

    _validate_phase3_metadata_contract(run_id=run_id, runmeta=runmeta_v1)

    if args.feature_mode == "univariate" and baselines_obj.get("skipped"):
        raise Phase3BaselineComparisonSkippedError(
            "phase3 baseline comparison skipped: univariate mode requires baseline report"
        )

    payload: dict[str, Any] = {
        "run_id": run_id,
        "backend": BACKEND,
        "config": config_snapshot,
        "metrics": results["metrics"],
        "baselines": baselines_obj,
        "checkpoints": {
            "best": str(best_ckpt),
            "last": str(last_ckpt),
        },
        "preprocessor": str(preprocessor_path) if preprocessor_path else None,
        "split_indices": split_indices,
        "inference": {
            "x_shape": list(x_last.shape),
            "y_true_last": y_true_last.tolist(),
            "y_pred_last": y_pred_last.tolist(),
            "predictions_csv": str(predictions_path),
        },
        "timestamps": {
            "start": results.get("start_time"),
            "end": results.get("end_time"),
            "saved_at": datetime.now().isoformat(),
        },
        "commit_hash": run_metadata.get("commit_hash"),
        "commit_hash_source": run_metadata.get("commit_hash_source"),
        "metadata_path": str(metadata_path),
        "runmeta_path": str(runmeta_path),
        "covariate_schema": covariate_contract,
    }

    _write_json(metrics_path, payload)
    _write_json(baseline_path, baselines_obj)
    _write_json(split_path, split_indices)
    _write_json(config_snapshot_path, config_snapshot)
    _write_json(metadata_path, run_metadata)
    if args.save_run_meta:
        _write_json(runmeta_path, runmeta_v1)

    cmdline = " ".join(sys.argv)

    report = f"""# Spline-LSTM Run Report

- run_id: `{run_id}`
- backend: `{BACKEND}`
- model_type: `{args.model_type}`
- feature_mode: `{args.feature_mode}`

## Command
- `{cmdline}`

## Config
- sequence_length: {args.sequence_length}
- horizon: {args.horizon}
- hidden_units: {args.hidden_units}
- dropout: {args.dropout}
- learning_rate: {args.learning_rate}
- epochs: {args.epochs}
- batch_size: {args.batch_size}
- normalize: {args.normalize} ({args.normalize_method})
- seed: {args.seed}

## Evaluation Metrics
- MAE: {results["metrics"]["mae"]:.6f}
- MSE: {results["metrics"]["mse"]:.6f}
- RMSE: {results["metrics"]["rmse"]:.6f}
- MAPE: {results["metrics"]["mape"]:.4f}
- MAPE (zero-safe): {results["metrics"].get("mape_zero_safe", float("nan")):.4f}
- MASE: {results["metrics"].get("mase", float("nan")):.6f}
- R2: {results["metrics"]["r2"]:.6f}

## Baseline Comparison
- Naive(last) RMSE: {baselines_obj.get("naive_last", {}).get("rmse", "n/a")}
- MA({args.ma_window or args.sequence_length}) RMSE: {baselines_obj.get("metrics", {}).get("baseline", {}).get("ma", {}).get("rmse", "n/a")}

## Inference (latest test window)
- y_true_last: {y_true_last.tolist()}
- y_pred_last: {y_pred_last.tolist()}

## Reproducibility Artifacts
- split indices: `{split_path}`
- config snapshot: `{config_snapshot_path}`
- commit hash: `{run_metadata.get("commit_hash")}` (source: `{run_metadata.get("commit_hash_source")}`)
- metadata(commit+seed): `{metadata_path}`
- run metadata(v1): `{runmeta_path}`

## Artifacts
- checkpoints/best: `{best_ckpt}`
- checkpoints/last: `{last_ckpt}`
- predictions: `{predictions_path}`
- metrics: `{metrics_path}`
- baselines: `{baseline_path}`
- report: `{report_path}`
"""
    _write_report(report_path, report)

    logger.info("Run complete: %s", run_id)
    return payload


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Spline-LSTM train/eval/infer runner")
    p.add_argument("--run-id", type=str, default=None)
    p.add_argument(
        "--run-id-validation",
        type=str,
        choices=["legacy", "strict"],
        default="legacy",
        help="run_id validation mode (default: legacy for backward compatibility)",
    )
    p.add_argument("--artifacts-dir", type=str, default="artifacts")
    p.add_argument(
        "--checkpoints-dir",
        type=str,
        default=None,
        help="Optional checkpoint base dir (legacy compatibility); default: <artifacts-dir>/checkpoints",
    )

    p.add_argument("--processed-npz", type=str, default=None, help="Path to preprocessing output .npz")
    p.add_argument(
        "--preprocessor-pkl",
        type=str,
        default=None,
        help=(
            "Optional explicit preprocessor path for run_id integrity checks. "
            "If omitted and --processed-npz matches artifacts layout, inferred automatically."
        ),
    )
    p.add_argument("--input-npy", type=str, default=None, help="Path to raw 1D series .npy")
    p.add_argument(
        "--synthetic",
        action="store_true",
        default=False,
        help="Legacy compatibility flag. Synthetic data is used by default when no input is provided.",
    )
    p.add_argument("--synthetic-samples", type=int, default=800)
    p.add_argument("--synthetic-noise", type=float, default=0.08)

    p.add_argument("--sequence-length", type=int, default=24)
    p.add_argument("--horizon", type=int, default=1)
    p.add_argument("--hidden-units", type=int, nargs="+", default=[64, 32])
    p.add_argument("--dropout", type=float, default=0.2)
    p.add_argument("--learning-rate", type=float, default=1e-3)

    # Phase 5 extension contract (backward compatible defaults)
    p.add_argument("--model-type", type=str, choices=["lstm", "gru", "attention_lstm"], default="lstm")
    p.add_argument("--feature-mode", type=str, choices=["univariate", "multivariate"], default="univariate")
    p.add_argument("--target-cols", type=str, default="target")
    p.add_argument("--dynamic-covariates", type=str, default="")
    p.add_argument("--future-covariates", type=str, default="")
    p.add_argument("--static-covariates", type=str, default="")
    p.add_argument("--covariate-spec", type=str, default=None)
    p.add_argument("--cv-splits", type=int, default=0, help="Number of splits for time-series cross-validation")
    p.add_argument("--export-formats", type=str, default="none")

    p.add_argument("--epochs", type=int, default=10)
    p.add_argument("--batch-size", type=int, default=32)
    p.add_argument("--test-size", type=float, default=0.2)
    p.add_argument("--val-size", type=float, default=0.2)

    p.add_argument("--normalize", action="store_true", default=True)
    p.add_argument("--no-normalize", action="store_false", dest="normalize")
    p.add_argument("--normalize-method", type=str, choices=["minmax", "standard"], default="minmax")

    p.add_argument("--early-stopping", action="store_true", default=True)
    p.add_argument("--no-early-stopping", action="store_false", dest="early_stopping")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument(
        "--ma-window", type=int, default=None, help="Moving-average baseline window (default: sequence-length)"
    )
    p.add_argument(
        "--deterministic",
        action="store_true",
        default=True,
        help="Enable deterministic backend settings when supported.",
    )
    p.add_argument("--no-deterministic", action="store_false", dest="deterministic")
    p.add_argument("--save-run-meta", action="store_true", default=True)
    p.add_argument("--no-save-run-meta", action="store_false", dest="save_run_meta")
    p.add_argument("--verbose", type=int, default=1)

    return p


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
    parser = build_parser()
    try:
        args = parser.parse_args()
    except SystemExit as exc:
        # argparse exits with code=2 for invalid arguments
        raise SystemExit(20) from exc

    set_global_seed(args.seed, deterministic=args.deterministic)

    try:
        out = run(args)
        print(json.dumps(out, indent=2, ensure_ascii=False))
    except Exception as exc:  # pragma: no cover - exercised via CLI tests
        error_payload = _build_error_payload(exc)
        code = int(error_payload["exit_code"])
        logger.error(
            "RUNNER_FAILURE code=%s error_code=%s message=%s",
            code,
            error_payload["error"]["code"],
            error_payload["error"]["message"],
        )
        print(json.dumps(error_payload, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(code) from exc


if __name__ == "__main__":
    main()
