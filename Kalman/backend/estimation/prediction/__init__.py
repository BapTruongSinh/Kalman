"""
``estimation.prediction`` — prediction adapter contract and ARX baseline.

Public API
----------
``PredictionInput``        — input window passed to ``predict()``
``PredictionResult``       — typed result returned by ``predict()``
``PredictionAdapter``      — abstract base class for all prediction models
``ARXTrainConfig``         — hyperparameters for offline ARX training
``ARXPredictionAdapter``   — ARX (OLS) implementation of ``PredictionAdapter``
"""

from .arx_adapter import ARXPredictionAdapter, ARXTrainConfig
from .base import PredictionAdapter, PredictionInput, PredictionResult

__all__ = [
    "PredictionInput",
    "PredictionResult",
    "PredictionAdapter",
    "ARXTrainConfig",
    "ARXPredictionAdapter",
]
