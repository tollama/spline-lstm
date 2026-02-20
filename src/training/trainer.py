"""Training pipeline for time series models."""

import numpy as np
from typing import Optional, Tuple, Dict, Any, Callable
import logging
from datetime import datetime
import json
import os
from pathlib import Path
from src.utils.run_id import validate_run_id

logger = logging.getLogger(__name__)


class Trainer:
    """Training pipeline for time series forecasting models."""

    @staticmethod
    def _validate_split_params(test_size: float, val_size: float) -> None:
        if not (0 < test_size < 1):
            raise ValueError(f"test_size must be in (0, 1), got {test_size}")
        if not (0 < val_size < 1):
            raise ValueError(f"val_size must be in (0, 1), got {val_size}")

    def __init__(
        self,
        model: Any,
        sequence_length: int = 24,
        prediction_horizon: int = 1,
        save_dir: str = "./checkpoints"
    ):
        self.model = model
        self.sequence_length = sequence_length
        self.prediction_horizon = prediction_horizon
        self.save_dir = save_dir
        self.metrics = {}
        self.split_indices = {}

        os.makedirs(save_dir, exist_ok=True)

    def create_sequences(
        self,
        data: np.ndarray,
        sequence_length: Optional[int] = None,
        horizon: Optional[int] = None
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Create sequences for training.

        Returns:
            X shape: [batch, lookback, features]
            y shape: [batch, horizon * features]
        """
        seq_len = sequence_length or self.sequence_length
        pred_horizon = horizon or self.prediction_horizon

        if seq_len <= 0 or pred_horizon <= 0:
            raise ValueError("sequence_length and horizon must be positive integers")

        if data.ndim == 1:
            data = data.reshape(-1, 1)
        if data.ndim != 2:
            raise ValueError(f"data must be 1D or 2D array, got shape={data.shape}")

        X, y = [], []

        for i in range(len(data) - seq_len - pred_horizon + 1):
            X.append(data[i:i + seq_len])
            y.append(data[i + seq_len:i + seq_len + pred_horizon])

        X = np.array(X)
        y = np.array(y).reshape(-1, pred_horizon * data.shape[1])

        logger.info(f"Created {len(X)} sequences")
        return X, y

    def train_test_split(
        self,
        X: np.ndarray,
        y: np.ndarray,
        test_size: float = 0.2
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Split data into train and test sets (chronological)."""
        split_idx = int(len(X) * (1 - test_size))

        X_train, X_test = X[:split_idx], X[split_idx:]
        y_train, y_test = y[:split_idx], y[split_idx:]

        logger.info(f"Train: {len(X_train)}, Test: {len(X_test)}")
        return X_train, X_test, y_train, y_test

    def split_series(
        self,
        data: np.ndarray,
        test_size: float = 0.2,
        val_size: float = 0.2
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Split raw series into train/val/test chronologically."""
        self._validate_split_params(test_size=test_size, val_size=val_size)

        n = len(data)
        train_end = int(n * (1 - test_size))
        trainval = data[:train_end]
        test = data[train_end:]

        val_start = int(len(trainval) * (1 - val_size))
        train = trainval[:val_start]
        val = trainval[val_start:]

        self.split_indices = {
            "n_total": int(n),
            "train": {"start": 0, "end": int(val_start)},
            "val": {"start": int(val_start), "end": int(train_end)},
            "test": {"start": int(train_end), "end": int(n)},
            "ratios": {"test_size": float(test_size), "val_size": float(val_size)},
        }

        logger.info("Raw split sizes - train: %d, val: %d, test: %d", len(train), len(val), len(test))
        return train, val, test

    def fit_normalizer(
        self,
        data: np.ndarray,
        method: str = 'minmax'
    ) -> Dict:
        """Fit normalization parameters on training split only."""
        if method == 'minmax':
            min_val = np.min(data)
            max_val = np.max(data)
            return {'method': 'minmax', 'min': min_val, 'max': max_val}
        else:  # standard
            mean_val = np.mean(data)
            std_val = np.std(data)
            return {'method': 'standard', 'mean': mean_val, 'std': std_val}

    def normalize(
        self,
        data: np.ndarray,
        params: Dict
    ) -> np.ndarray:
        """Transform data with pre-fitted normalization parameters."""
        if params['method'] == 'minmax':
            return (data - params['min']) / (params['max'] - params['min'] + 1e-8)
        return (data - params['mean']) / (params['std'] + 1e-8)

    def denormalize(
        self,
        data: np.ndarray,
        params: Dict
    ) -> np.ndarray:
        """Denormalize data."""
        if params['method'] == 'minmax':
            return data * (params['max'] - params['min']) + params['min']
        else:
            return data * params['std'] + params['mean']

    def compute_metrics(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray
    ) -> Dict[str, float]:
        """Compute evaluation metrics, including robust MAPE and MASE."""
        mae = np.mean(np.abs(y_true - y_pred))
        mse = np.mean((y_true - y_pred) ** 2)
        rmse = np.sqrt(mse)

        mask = y_true != 0
        mape = np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100 if mask.sum() > 0 else np.inf

        # MASE: mean absolute scaled error based on a naive one-step forecast
        # Use the first feature of the target for naive baseline
        if y_true.shape[0] > 1:
            if y_true.ndim == 2:
                naive_diff = np.abs(y_true[1:, 0] - y_true[:-1, 0])
            else:
                naive_diff = np.abs(y_true[1:, :, 0] - y_true[:-1, :, 0])
            naive_mae = np.mean(naive_diff)
        else:
            naive_mae = np.inf
        mase = mae / naive_mae if naive_mae > 0 else np.inf

        ss_res = np.sum((y_true - y_pred) ** 2)
        ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
        r2 = 1 - (ss_res / (ss_tot + 1e-8))

        return {
            'mae': float(mae),
            'mse': float(mse),
            'rmse': float(rmse),
            'mape': float(mape),
            'mase': float(mase),
            'r2': float(r2)
        }


    def train(
        self,
        data: np.ndarray,
        epochs: int = 100,
        batch_size: int = 32,
        test_size: float = 0.2,
        val_size: float = 0.2,
        normalize: bool = True,
        normalize_method: str = 'minmax',
        early_stopping: bool = True,
        verbose: int = 1,
        extra_callbacks: Optional[list] = None,
        extra_metric_fns: Optional[Dict[str, Callable[[np.ndarray, np.ndarray], float]]] = None
    ) -> Dict[str, Any]:
        """Full training pipeline with leakage-safe split/normalization."""
        if data is None:
            raise ValueError("data must not be None")
        data = np.asarray(data)
        if data.size == 0:
            raise ValueError("data must not be empty")
        if not np.isfinite(data).all():
            raise ValueError("data contains NaN/Inf values")

        self._validate_split_params(test_size=test_size, val_size=val_size)

        results = {
            'start_time': datetime.now().isoformat(),
            'config': {
                'sequence_length': self.sequence_length,
                'prediction_horizon': self.prediction_horizon,
                'epochs': epochs,
                'batch_size': batch_size,
                'test_size': test_size,
                'val_size': val_size,
                'normalize_method': normalize_method,
            }
        }

        train_raw, val_raw, test_raw = self.split_series(data, test_size=test_size, val_size=val_size)

        if normalize:
            norm_params = self.fit_normalizer(train_raw, method=normalize_method)
            train_raw = self.normalize(train_raw, norm_params)
            val_raw = self.normalize(val_raw, norm_params)
            test_raw = self.normalize(test_raw, norm_params)
            results['normalization'] = norm_params
            self.norm_params = norm_params

        X_train, y_train = self.create_sequences(train_raw)
        X_val, y_val = self.create_sequences(val_raw)
        X_test, y_test = self.create_sequences(test_raw)

        if len(X_train) == 0 or len(X_val) == 0 or len(X_test) == 0:
            raise ValueError(
                "Insufficient data after split to create train/val/test sequences. "
                "Adjust sequence_length, prediction_horizon, test_size, or val_size."
            )

        history = self.model.fit_model(
            X_train,
            y_train,
            epochs=epochs,
            batch_size=batch_size,
            validation_data=(X_val, y_val),
            early_stopping=early_stopping,
            shuffle=False,
            verbose=verbose,
            extra_callbacks=extra_callbacks,
        )

        y_pred = self.model.predict(X_test)
        metrics = self.compute_metrics(y_test, y_pred)

        if extra_metric_fns:
            for name, fn in extra_metric_fns.items():
                metrics[name] = float(fn(y_test, y_pred))

        results['end_time'] = datetime.now().isoformat()
        results['history'] = history
        results['metrics'] = metrics
        results['split_indices'] = self.split_indices

        self.metrics = metrics
        self.X_test = X_test
        self.y_test = y_test
        self.y_pred = y_pred

        logger.info(f"Training complete. RMSE: {metrics['rmse']:.4f}, R²: {metrics['r2']:.4f}")

        return results

    def save_checkpoint(self, name: str = None) -> str:
        """Save model checkpoint."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        raw_name = name or f"model_{timestamp}"
        ext = Path(raw_name).suffix.lower()
        ckpt_name = raw_name if ext in {".keras", ".h5"} else f"{raw_name}.keras"
        path = os.path.join(self.save_dir, ckpt_name)

        self.model.save(path)

        metrics_stem = Path(raw_name).stem
        metrics_path = os.path.join(self.save_dir, f"{metrics_stem}_metrics.json")
        with open(metrics_path, 'w') as f:
            json.dump(self.metrics, f, indent=2)

        logger.info(f"Checkpoint saved: {path}")
        return path

    @staticmethod
    def _validate_run_id(run_id: str) -> None:
        validate_run_id(run_id, mode="legacy")

    def save_run_artifacts(
        self,
        run_id: str,
        base_dir: str = "artifacts",
        config: Optional[Dict[str, Any]] = None,
        report: Optional[str] = None,
        preprocessor_blob: Optional[bytes] = None
    ) -> Dict[str, str]:
        """Save artifacts under run_id-scoped paths."""
        self._validate_run_id(run_id)

        base = Path(base_dir)
        model_dir = base / "models" / run_id
        metrics_dir = base / "metrics"
        configs_dir = base / "configs"
        reports_dir = base / "reports"

        for d in (model_dir, metrics_dir, configs_dir, reports_dir):
            d.mkdir(parents=True, exist_ok=True)

        model_path = model_dir / "model.keras"
        preprocessor_path = model_dir / "preprocessor.pkl"
        metrics_path = metrics_dir / f"{run_id}.json"
        config_path = configs_dir / f"{run_id}.yaml"
        report_path = reports_dir / f"{run_id}.md"

        self.model.save(str(model_path))

        with open(preprocessor_path, "wb") as f:
            f.write(preprocessor_blob if preprocessor_blob is not None else b"{}")

        with open(metrics_path, "w") as f:
            json.dump(self.metrics or {}, f, indent=2)

        with open(config_path, "w") as f:
            json.dump(config or {}, f, indent=2)

        with open(report_path, "w") as f:
            f.write(report or "# Run Report\n")

        return {
            "model": str(model_path),
            "preprocessor": str(preprocessor_path),
            "metrics": str(metrics_path),
            "config": str(config_path),
            "report": str(report_path),
        }

    @staticmethod
    def validate_artifact_run_id_match(model_path: str, preprocessor_path: str) -> bool:
        """Validate model/preprocessor run_id consistency from path layout."""
        model_parts = Path(model_path).parts
        prep_parts = Path(preprocessor_path).parts

        try:
            model_run_id = model_parts[model_parts.index("models") + 1]
            prep_run_id = prep_parts[prep_parts.index("models") + 1]
        except (ValueError, IndexError) as exc:
            raise ValueError("Invalid artifact path layout; expected .../models/{run_id}/...") from exc

        if model_run_id != prep_run_id:
            raise ValueError(
                f"run_id mismatch between model ({model_run_id}) and preprocessor ({prep_run_id})"
            )
        return True

    def load_checkpoint(self, path: str) -> None:
        """Load model checkpoint."""
        self.model.load(path)
        logger.info(f"Checkpoint loaded: {path}")
