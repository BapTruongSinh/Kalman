"""
``estimation.prediction``: hợp đồng prediction adapter và baseline ARX.

Public API
----------
``PredictionInput``        — cửa sổ input truyền vào ``predict()``
``PredictionResult``       — kết quả có kiểu trả về từ ``predict()``
``PredictionAdapter``      — abstract base class cho mọi model dự đoán
``ARXTrainConfig``         — siêu tham số để train ARX offline
``ARXPredictionAdapter``   — triển khai ARX (OLS) của ``PredictionAdapter``
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
