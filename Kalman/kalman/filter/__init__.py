"""
``kalman.filter``: Adaptive Kalman estimation cycle.

Public API
----------
``KalmanConfig``           — bộ siêu tham số frozen, mặc định theo ADR-003
``KalmanState``            — trạng thái bộ lọc được giữ giữa các bước
``CycleResult``            — đầu ra từng bước, chứa phần Kalman cần ghi ``PipelineCycle``
``AdaptiveKalmanCycle``    — estimator Soil_Moisture vô hướng với R thích nghi có chặn
"""

from .cycle import AdaptiveKalmanCycle, CycleResult, KalmanConfig, KalmanState

__all__ = [
    "KalmanConfig",
    "KalmanState",
    "CycleResult",
    "AdaptiveKalmanCycle",
]
