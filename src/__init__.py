"""Spline + LSTM Time Series Forecasting Library.

Keep top-level imports lazy so edge-only workflows can import submodules such
as `src.training.edge_release_gate` without pulling in TensorFlow or
preprocessing dependencies.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

__version__ = "0.2.0"

__all__ = [
    "LSTMModel",
    "GRUModel",
    "BidirectionalLSTMModel",
    "AttentionLSTMModel",
    "SplinePreprocessor",
    "Trainer",
]

_LAZY_IMPORTS = {
    "LSTMModel": ("src.models.lstm", "LSTMModel"),
    "GRUModel": ("src.models.lstm", "GRUModel"),
    "BidirectionalLSTMModel": ("src.models.lstm", "BidirectionalLSTMModel"),
    "AttentionLSTMModel": ("src.models.lstm", "AttentionLSTMModel"),
    "SplinePreprocessor": ("src.preprocessing.spline", "SplinePreprocessor"),
    "Trainer": ("src.training.trainer", "Trainer"),
}


def __getattr__(name: str) -> Any:
    target = _LAZY_IMPORTS.get(name)
    if target is None:
        raise AttributeError(f"module 'src' has no attribute {name!r}")
    module_name, attr_name = target
    module = import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
