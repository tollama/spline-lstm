"""
Example: Spline + LSTM Time Series Forecasting

This script demonstrates the basic usage of the Spline + LSTM library.

Install the package first: pip install -e .
"""

import numpy as np

from src import LSTMModel, SplinePreprocessor, Trainer


def generate_synthetic_data(n_samples: int = 1000, noise: float = 0.1):
    """Generate synthetic time series data."""
    t = np.linspace(0, 20 * np.pi, n_samples)
    y = np.sin(t) + 0.5 * np.sin(2 * t) + noise * np.random.randn(n_samples)
    
    # Add some missing values
    missing_mask = np.random.rand(n_samples) < 0.05
    y_missing = y.copy()
    y_missing[missing_mask] = np.nan
    
    return t, y, y_missing


def main():
    print("=" * 60)
    print("Spline + LSTM Time Series Forecasting Example")
    print("=" * 60)
    
    # Generate data
    print("\n[1] Generating synthetic data...")
    t, y_true, y_missing = generate_synthetic_data(1000, noise=0.1)
    print(f"    Samples: {len(t)}")
    print(f"    Missing: {np.isnan(y_missing).sum()} ({np.isnan(y_missing).sum()/len(y_missing)*100:.1f}%)")
    
    # Spline preprocessing
    print("\n[2] Spline preprocessing...")
    preprocessor = SplinePreprocessor(degree=3, smoothing_factor=0.3)
    
    # Interpolate missing values
    y_filled = preprocessor.interpolate_missing(y_missing)
    print(f"    Missing values interpolated: {np.isnan(y_filled).sum()}")
    
    # Smooth the data
    y_smooth = preprocessor.smooth(y_filled, window=5)
    
    # Extract features
    features = preprocessor.extract_features(y_smooth)
    print(f"    Features: mean={features['mean']:.4f}, std={features['std']:.4f}")
    
    # Prepare for LSTM
    print("\n[3] Creating sequences and training model...")
    model = LSTMModel(
        sequence_length=24,
        hidden_units=[64, 32],
        dropout=0.2,
        learning_rate=0.001
    )
    
    trainer = Trainer(model, sequence_length=24, prediction_horizon=1)
    
    results = trainer.train(
        y_smooth,
        epochs=50,
        batch_size=32,
        test_size=0.2,
        early_stopping=True,
        verbose=1
    )
    
    # Results
    print("\n[4] Training Results:")
    print(f"    MAE:  {results['metrics']['mae']:.4f}")
    print(f"    RMSE: {results['metrics']['rmse']:.4f}")
    print(f"    MAPE: {results['metrics']['mape']:.2f}%")
    print(f"    R²:   {results['metrics']['r2']:.4f}")
    
    # Save model
    print("\n[5] Saving model...")
    checkpoint_path = trainer.save_checkpoint("example_model.keras")
    print(f"    Model saved to: {checkpoint_path}")
    
    print("\n" + "=" * 60)
    print("Training complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()