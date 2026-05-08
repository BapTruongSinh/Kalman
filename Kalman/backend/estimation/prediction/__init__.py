"""
``estimation.prediction``: hợp đồng prediction adapter và baseline ARX.

Public API
----------
``PredictionInput``        — cửa sổ input truyền vào ``predict()``
``PredictionResult``       — kết quả có kiểu trả về từ ``predict()``
``PredictionAdapter``      — abstract base class cho mọi model dự đoán
``ARXArtifactConfig``      — cấu hình bậc và cột input của artifact ARX
``ARXPredictionAdapter``   — adapter ARX artifact-only cho runtime live
"""

from .arx_adapter import ARXArtifactConfig, ARXPredictionAdapter
from .base import PredictionAdapter, PredictionInput, PredictionResult

__all__ = [
    "PredictionInput",
    "PredictionResult",
    "PredictionAdapter",
    "ARXArtifactConfig",
    "ARXPredictionAdapter",
]
