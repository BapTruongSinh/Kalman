"""
``estimation.kalman`` — Adaptive Kalman-ready estimation cycle.

Public API
----------
``KalmanConfig``           — frozen hyperparameter set (ADR-003 defaults)
``KalmanState``            — mutable filter state carried between steps
``CycleResult``            — per-step output; contains the Kalman subset needed to populate ``PipelineCycle``
``AdaptiveKalmanCycle``    — scalar Soil_Moisture estimator with bounded adaptive R
"""

from .cycle import AdaptiveKalmanCycle, CycleResult, KalmanConfig, KalmanState

__all__ = [
    "KalmanConfig",
    "KalmanState",
    "CycleResult",
    "AdaptiveKalmanCycle",
]
