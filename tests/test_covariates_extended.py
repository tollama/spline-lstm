
import numpy as np
import pytest
import os
import sys

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.models.lstm import LSTMModel
from src.training.trainer import Trainer

@pytest.mark.skipif(
    not os.environ.get('RUN_ML_TESTS'),
    reason="ML tests require TensorFlow"
)
def test_lstm_with_all_covariates():
    """Test LSTM model with past, future, and static covariates."""
    seq_len = 10
    horizon = 3
    n_past_features = 2
    n_future_features = 1
    n_static_features = 4
    batch_size = 8

    # Create model
    model = LSTMModel(
        sequence_length=seq_len,
        output_units=horizon,
        input_features=n_past_features,
        future_features=n_future_features,
        static_features=n_static_features
    )
    model.build()
    assert model.model is not None

    # Dummy data
    X_past = np.random.rand(batch_size, seq_len, n_past_features).astype(np.float32)
    X_fut = np.random.rand(batch_size, horizon, n_future_features).astype(np.float32)
    X_stat = np.random.rand(batch_size, n_static_features).astype(np.float32)
    y = np.random.rand(batch_size, horizon).astype(np.float32)

    X_list = [X_past, X_fut, X_stat]

    # Test prediction
    y_pred = model.predict(X_list)
    assert y_pred.shape == (batch_size, horizon)

    # Test training (short run)
    trainer = Trainer(model, sequence_length=seq_len, prediction_horizon=horizon)
    results = trainer.train(X=X_list, y=y, epochs=1, batch_size=2, verbose=0)
    
    assert 'metrics' in results
    assert 'rmse' in results['metrics']

@pytest.mark.skipif(
    not os.environ.get('RUN_ML_TESTS'),
    reason="ML tests require TensorFlow"
)
def test_cross_validation_with_covariates():
    """Test cross-validation with covariate list input."""
    seq_len = 5
    horizon = 2
    n_past_features = 2
    n_future_features = 1
    n_static_features = 3
    n_samples = 20

    model = LSTMModel(
        sequence_length=seq_len,
        output_units=horizon,
        input_features=n_past_features,
        future_features=n_future_features,
        static_features=n_static_features
    )
    model.build()

    X_past = np.random.rand(n_samples, seq_len, n_past_features).astype(np.float32)
    X_fut = np.random.rand(n_samples, horizon, n_future_features).astype(np.float32)
    X_stat = np.random.rand(n_samples, n_static_features).astype(np.float32)
    y = np.random.rand(n_samples, horizon).astype(np.float32)

    X_list = [X_past, X_fut, X_stat]

    trainer = Trainer(model, sequence_length=seq_len, prediction_horizon=horizon)
    cv_results = trainer.cross_validate(X=X_list, y=y, n_splits=3, epochs=1, batch_size=4, verbose=0)
    
    assert 'avg_metrics' in cv_results
    assert 'folds' in cv_results
    assert len(cv_results['folds']) == 3
