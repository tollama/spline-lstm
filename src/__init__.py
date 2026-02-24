"""Spline + LSTM Time Series Forecasting Library."""

__version__ = "0.1.0"

from .models.lstm import BidirectionalLSTMModel, LSTMModel
from .preprocessing.spline import SplinePreprocessor
from .training.trainer import Trainer

__all__ = [
    "LSTMModel",
    "BidirectionalLSTMModel",
    "SplinePreprocessor",
    "Trainer",
]
