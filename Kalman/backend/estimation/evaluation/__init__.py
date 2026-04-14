"""
estimation.evaluation — Evaluation metrics and report export.

Pure metric layer (no Django required)
---------------------------------------
    from estimation.evaluation.metrics import compute_metrics, SliceMetrics

DB integration and export (requires Django settings)
------------------------------------------------------
    from estimation.evaluation import evaluate_slice, evaluate_all_slices
    from estimation.evaluation import build_text_report, export_to_csv, export_plots

Threshold constants (importable without Django)
------------------------------------------------
    VARIANCE_REDUCTION_MIN  0.20  (ADR-003)
    RMSE_RATIO_MAX          1.05  (ADR-003)
    MAE_RATIO_MAX           1.05  (ADR-003)
"""
from estimation.evaluation.metrics import (
    MAE_RATIO_MAX,
    RMSE_RATIO_MAX,
    VARIANCE_REDUCTION_MIN,
    SliceMetrics,
    compute_metrics,
)

# DB-backed functions are loaded on first attribute access so that importing
# SliceMetrics / compute_metrics works without Django settings configured.
_REPORTER_ATTRS = frozenset(
    {
        "evaluate_slice",
        "evaluate_all_slices",
        "build_text_report",
        "export_to_csv",
        "export_plots",
    }
)


def __getattr__(name: str):  # noqa: ANN001
    if name in _REPORTER_ATTRS:
        from estimation.evaluation import reporter as _r  # noqa: PLC0415

        return getattr(_r, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # Pure metrics
    "SliceMetrics",
    "compute_metrics",
    # Thresholds
    "VARIANCE_REDUCTION_MIN",
    "RMSE_RATIO_MAX",
    "MAE_RATIO_MAX",
    # DB integration (lazy)
    "evaluate_slice",
    "evaluate_all_slices",
    # Export (lazy)
    "build_text_report",
    "export_to_csv",
    "export_plots",
]
