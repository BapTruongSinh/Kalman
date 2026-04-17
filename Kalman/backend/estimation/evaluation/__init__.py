"""
estimation.evaluation: metric đánh giá và export báo cáo.

Tầng metric thuần, không cần Django
-----------------------------------
    from estimation.evaluation.metrics import compute_metrics, SliceMetrics

Tích hợp DB và export, cần Django settings
------------------------------------------
    from estimation.evaluation import evaluate_slice, evaluate_all_slices
    from estimation.evaluation import build_text_report, export_to_csv, export_plots

Hằng số ngưỡng, import được mà không cần Django
-----------------------------------------------
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

# Các hàm cần DB được load lazy khi truy cập attribute lần đầu, để import
# SliceMetrics / compute_metrics vẫn chạy được khi chưa cấu hình Django settings.
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
    # Metric thuần
    "SliceMetrics",
    "compute_metrics",
    # Ngưỡng
    "VARIANCE_REDUCTION_MIN",
    "RMSE_RATIO_MAX",
    "MAE_RATIO_MAX",
    # Tích hợp DB, load lazy
    "evaluate_slice",
    "evaluate_all_slices",
    # Export, load lazy
    "build_text_report",
    "export_to_csv",
    "export_plots",
]
