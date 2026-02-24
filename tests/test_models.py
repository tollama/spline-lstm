"""Unit tests for Spline + LSTM models."""

import os
import sys

import numpy as np
import pytest

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from preprocessing.spline import SplinePreprocessor


class TestSplinePreprocessor:
    """Tests for SplinePreprocessor."""

    def test_fit_transform(self):
        """Test fit and transform."""
        x = np.linspace(0, 10, 100)
        y = np.sin(x) + np.random.normal(0, 0.1, 100)

        preprocessor = SplinePreprocessor(degree=3)
        y_smooth = preprocessor.fit_transform(x, y)

        assert len(y_smooth) == len(y)
        assert not np.any(np.isnan(y_smooth))

    def test_interpolate_missing(self):
        """Test missing value interpolation."""
        y = np.array([1, 2, np.nan, 4, 5, np.nan, 7, 8, 9, 10])

        preprocessor = SplinePreprocessor()
        y_filled = preprocessor.interpolate_missing(y)

        assert not np.any(np.isnan(y_filled))

    def test_extract_features(self):
        """Test feature extraction."""
        y = np.sin(np.linspace(0, 10, 100))

        preprocessor = SplinePreprocessor()
        features = preprocessor.extract_features(y)

        assert "mean" in features
        assert "std" in features
        assert "min" in features
        assert "max" in features


class TestLSTMModel:
    """Tests for LSTM models."""

    @pytest.mark.skipif(not os.environ.get("RUN_ML_TESTS"), reason="ML tests require TensorFlow")
    def test_lstm_build(self):
        """Test LSTM model building."""
        from models.lstm import LSTMModel

        model = LSTMModel(sequence_length=24, hidden_units=[64, 32], dropout=0.2)
        model.build()

        assert model.model is not None

    @pytest.mark.skipif(not os.environ.get("RUN_ML_TESTS"), reason="ML tests require TensorFlow")
    def test_lstm_train(self):
        """Test LSTM training."""
        from models.lstm import LSTMModel
        from training.trainer import Trainer

        # Generate synthetic data
        data = np.sin(np.linspace(0, 50, 500))

        model = LSTMModel(sequence_length=24, hidden_units=[32, 16])
        trainer = Trainer(model, sequence_length=24)

        results = trainer.train(data, epochs=5, verbose=0)

        assert "metrics" in results
        assert "rmse" in results["metrics"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
