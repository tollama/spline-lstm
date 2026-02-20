"""Scaling and split utilities for preprocessing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

import numpy as np


@dataclass
class StandardScaler1D:
    mean_: float = 0.0
    std_: float = 1.0
    fitted_: bool = False

    def fit(self, y: np.ndarray) -> "StandardScaler1D":
        arr = np.asarray(y, dtype=float)
        self.mean_ = float(np.mean(arr))
        self.std_ = float(np.std(arr))
        if self.std_ <= 0:
            self.std_ = 1.0
        self.fitted_ = True
        return self

    def transform(self, y: np.ndarray) -> np.ndarray:
        if not self.fitted_:
            raise RuntimeError("Scaler not fitted")
        arr = np.asarray(y, dtype=float)
        return (arr - self.mean_) / self.std_

    def inverse_transform(self, y: np.ndarray) -> np.ndarray:
        if not self.fitted_:
            raise RuntimeError("Scaler not fitted")
        arr = np.asarray(y, dtype=float)
        return arr * self.std_ + self.mean_

    def to_dict(self) -> Dict[str, float]:
        return {"type": "standard", "mean": self.mean_, "std": self.std_}


@dataclass
class MinMaxScaler1D:
    min_: float = 0.0
    max_: float = 1.0
    fitted_: bool = False

    def fit(self, y: np.ndarray) -> "MinMaxScaler1D":
        arr = np.asarray(y, dtype=float)
        self.min_ = float(np.min(arr))
        self.max_ = float(np.max(arr))
        if self.max_ <= self.min_:
            self.max_ = self.min_ + 1.0
        self.fitted_ = True
        return self

    def transform(self, y: np.ndarray) -> np.ndarray:
        if not self.fitted_:
            raise RuntimeError("Scaler not fitted")
        arr = np.asarray(y, dtype=float)
        return (arr - self.min_) / (self.max_ - self.min_)

    def inverse_transform(self, y: np.ndarray) -> np.ndarray:
        if not self.fitted_:
            raise RuntimeError("Scaler not fitted")
        arr = np.asarray(y, dtype=float)
        return arr * (self.max_ - self.min_) + self.min_

    def to_dict(self) -> Dict[str, float]:
        return {"type": "minmax", "min": self.min_, "max": self.max_}


def build_scaler(method: str = "standard"):
    m = method.lower().strip()
    if m == "standard":
        return StandardScaler1D()
    if m == "minmax":
        return MinMaxScaler1D()
    raise ValueError(f"unsupported scaling method: {method}")


def chronological_split(
    y: np.ndarray,
    train_ratio: float = 0.7,
    val_ratio: float = 0.15,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, Tuple[int, int]]:
    """Chronological train/val/test split for 1D series."""
    if not (0 < train_ratio < 1) or not (0 <= val_ratio < 1):
        raise ValueError("invalid split ratios")
    if train_ratio + val_ratio >= 1:
        raise ValueError("train_ratio + val_ratio must be < 1")

    arr = np.asarray(y, dtype=float)
    n = len(arr)
    train_end = int(n * train_ratio)
    val_end = int(n * (train_ratio + val_ratio))
    if train_end <= 0 or val_end <= train_end or val_end >= n:
        raise ValueError("series too short for requested split ratios")

    return arr[:train_end], arr[train_end:val_end], arr[val_end:], (train_end, val_end)
