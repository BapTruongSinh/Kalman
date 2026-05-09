"""
Tính toán metric đánh giá thuần túy.

Hàm nhận dict thường (từ QuerySet.values()), nên tầng tính toán không phụ thuộc
Django hoặc DB và có thể unit test bằng dữ liệu giả.

Ngưỡng chấp nhận ADR-003
------------------------
variance_reduction  >= 0.20  (20 %)
rmse_ratio          <= 1.05
mae_ratio           <= 1.05
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

import numpy as np

# ── Ngưỡng chấp nhận ADR-003 ─────────────────────────────────────────────────
VARIANCE_REDUCTION_MIN: float = 0.20
RMSE_RATIO_MAX: float = 1.05
MAE_RATIO_MAX: float = 1.05


@dataclass(frozen=True)
class SliceMetrics:
    """Tất cả metric đánh giá cho online segment của một live run.

    Thuộc tính suy ra
    -----------------
    cycle_success_rate : n_valid / n_samples
    sample_loss_rate   : (n_skipped + n_error) / n_samples
    passes_acceptance_gate : True if all three ADR-003 flags are True
    """

    # ── Số lượng sample ──────────────────────────────────────────────────────
    n_samples: int = 0
    n_valid: int = 0
    n_skipped: int = 0
    n_error: int = 0

    # ── Phân bố trạng thái adaptive ──────────────────────────────────────────
    n_r_updated: int = 0
    n_r_skipped: int = 0
    n_adaptive_skipped: int = 0

    # ── Độ trễ ───────────────────────────────────────────────────────────────
    latency_mean_ms: Optional[float] = None
    latency_p95_ms: Optional[float] = None

    # ── Độ chính xác ARX, khi có arx_predicted và reference ─────────────────
    rmse_arx: Optional[float] = None
    mae_arx: Optional[float] = None

    # ── Độ chính xác Kalman, khi có kf_x_posterior và reference ─────────────
    rmse_filtered: Optional[float] = None
    mae_filtered: Optional[float] = None

    # ── Mức giảm phương sai ──────────────────────────────────────────────────
    var_diff_raw: Optional[float] = None
    var_diff_filtered: Optional[float] = None
    variance_reduction: Optional[float] = None

    # ── Tỷ lệ guardrail ──────────────────────────────────────────────────────
    rmse_ratio: Optional[float] = None
    mae_ratio: Optional[float] = None

    # ── Chẩn đoán innovation ────────────────────────────────────────────────
    innovation_mean: Optional[float] = None
    innovation_std: Optional[float] = None
    innovation_max_abs: Optional[float] = None

    # ── Chẩn đoán R thích nghi ──────────────────────────────────────────────
    R_mean: Optional[float] = None
    R_min_observed: Optional[float] = None
    R_max_observed: Optional[float] = None

    # ── Hiệp phương sai posterior ────────────────────────────────────────────
    P_mean: Optional[float] = None
    P_max: Optional[float] = None

    # ── Cờ pass / fail theo ADR-003 ─────────────────────────────────────────
    pass_variance_reduction: Optional[bool] = None
    pass_rmse_guardrail: Optional[bool] = None
    pass_mae_guardrail: Optional[bool] = None

    # ── Thuộc tính suy ra ───────────────────────────────────────────────────

    @property
    def cycle_success_rate(self) -> Optional[float]:
        """Tỷ lệ cycle hoàn tất bình thường (n_valid / n_samples)."""
        if self.n_samples == 0:
            return None
        return self.n_valid / self.n_samples

    @property
    def sample_loss_rate(self) -> Optional[float]:
        """Tỷ lệ sample mất do bị skip hoặc lỗi."""
        if self.n_samples == 0:
            return None
        return (self.n_skipped + self.n_error) / self.n_samples

    @property
    def passes_acceptance_gate(self) -> bool:
        """True khi cả ba tiêu chí chấp nhận ADR-003 đều pass."""
        return bool(
            self.pass_variance_reduction
            and self.pass_rmse_guardrail
            and self.pass_mae_guardrail
        )


# ── Tính toán ────────────────────────────────────────────────────────────────


def compute_metrics(rows: Sequence[dict]) -> SliceMetrics:
    """Tính toàn bộ metric đánh giá từ chuỗi dict của các dòng cycle.

    Parameters
    ----------
    rows:
        Dict sinh bởi ``PipelineCycle.objects.values(...)``.
        Các key kỳ vọng, đều có thể optional / nullable:
        ``raw_soil_moisture``, ``arx_predicted``, ``kf_x_prior``,
        ``kf_P_prior``, ``kf_innovation``, ``kf_R``, ``kf_K``,
        ``kf_x_posterior``, ``kf_P_posterior``,
        ``cycle_status``, ``adaptive_status``, ``latency_ms``.

    Returns
    -------
    SliceMetrics
        Immutable dataclass with every computed metric.  Fields are ``None``
        Dataclass bất biến chứa toàn bộ metric đã tính. Field là ``None`` khi
        dữ liệu không đủ, ví dụ không có dự đoán ARX.

    Ghi chú
    -------
    * Mọi phép tổng hợp scalar (latency, innovation, R, P) dùng
      :func:`_finite_values`, loại ``None``, ``NaN`` và ``Inf`` trước khi tạo
      numpy array.
    * Variance reduction được tính trên các dòng **paired**: chỉ lấy dòng mà cả
      ``raw_soil_moisture`` và ``kf_x_posterior`` đều hữu hạn. Như vậy hai chuỗi
      ``np.diff`` dùng cùng index sample, tỷ lệ mới có ý nghĩa cho gate ADR-003.
    """
    if not rows:
        return SliceMetrics()

    n_samples = len(rows)
    n_valid = sum(1 for r in rows if r.get("cycle_status") == "ok")
    n_skipped = sum(
        1 for r in rows if r.get("cycle_status", "").startswith("skipped")
    )
    n_error = sum(1 for r in rows if r.get("cycle_status") == "error")

    # ── Phân bố trạng thái adaptive ─────────────────────────────────────────
    n_r_updated = sum(1 for r in rows if r.get("adaptive_status") == "R_updated")
    n_r_skipped = sum(1 for r in rows if r.get("adaptive_status") == "R_skipped")
    n_adaptive_skipped = sum(1 for r in rows if r.get("adaptive_status") == "skipped")

    # ── Độ trễ ──────────────────────────────────────────────────────────────
    lat_arr = _finite_values(rows, "latency_ms")
    if len(lat_arr) > 0:
        latency_mean_ms = float(np.mean(lat_arr))
        latency_p95_ms = float(np.percentile(lat_arr, 95))
    else:
        latency_mean_ms = latency_p95_ms = None

    # ── Metric độ chính xác, chỉ tính cycle ok có reference ─────────────────
    ok_rows = [r for r in rows if r.get("cycle_status") == "ok"]

    arx_refs, arx_preds = _paired_values(ok_rows, "raw_soil_moisture", "arx_predicted")
    if len(arx_refs) >= 2:
        rmse_arx = _rmse(arx_refs, arx_preds)
        mae_arx = _mae(arx_refs, arx_preds)
    else:
        rmse_arx = mae_arx = None

    kf_refs, kf_filtered = _paired_values(ok_rows, "raw_soil_moisture", "kf_x_posterior")
    if len(kf_refs) >= 2:
        rmse_filtered = _rmse(kf_refs, kf_filtered)
        mae_filtered = _mae(kf_refs, kf_filtered)
    else:
        rmse_filtered = mae_filtered = None

    # ── Mức giảm phương sai ──────────────────────────────────────────────────
    # Dùng _paired_values để raw_vals[i] và filt_vals[i] luôn cùng một dòng.
    # Nếu một trong hai cột không hữu hạn thì bỏ dòng đó khỏi cả hai array, nhờ
    # vậy hai chuỗi diff vẫn căn đúng với nhau.
    raw_vals, filt_vals = _paired_values(rows, "raw_soil_moisture", "kf_x_posterior")

    var_diff_raw = float(np.var(np.diff(raw_vals))) if len(raw_vals) >= 2 else None
    var_diff_filtered = float(np.var(np.diff(filt_vals))) if len(filt_vals) >= 2 else None

    if var_diff_raw is not None and var_diff_raw > 0 and var_diff_filtered is not None:
        variance_reduction = 1.0 - (var_diff_filtered / var_diff_raw)
    else:
        variance_reduction = None

    # ── Tỷ lệ guardrail ─────────────────────────────────────────────────────
    rmse_ratio = (
        rmse_filtered / rmse_arx
        if (rmse_filtered is not None and rmse_arx is not None and rmse_arx > 0)
        else None
    )
    mae_ratio = (
        mae_filtered / mae_arx
        if (mae_filtered is not None and mae_arx is not None and mae_arx > 0)
        else None
    )

    # ── Chẩn đoán innovation ───────────────────────────────────────────────
    innovations = _finite_values(rows, "kf_innovation")
    if len(innovations) > 0:
        innovation_mean = float(np.mean(innovations))
        innovation_std = float(np.std(innovations))
        innovation_max_abs = float(np.max(np.abs(innovations)))
    else:
        innovation_mean = innovation_std = innovation_max_abs = None

    # ── Chẩn đoán R thích nghi ─────────────────────────────────────────────
    r_vals = _finite_values(rows, "kf_R")
    if len(r_vals) > 0:
        R_mean = float(np.mean(r_vals))
        R_min_observed = float(np.min(r_vals))
        R_max_observed = float(np.max(r_vals))
    else:
        R_mean = R_min_observed = R_max_observed = None

    # ── Hiệp phương sai posterior ───────────────────────────────────────────
    p_vals = _finite_values(rows, "kf_P_posterior")
    if len(p_vals) > 0:
        P_mean = float(np.mean(p_vals))
        P_max = float(np.max(p_vals))
    else:
        P_mean = P_max = None

    # ── Pass / fail theo ADR-003 ────────────────────────────────────────────
    pass_variance_reduction = (
        variance_reduction >= VARIANCE_REDUCTION_MIN
        if variance_reduction is not None
        else None
    )
    pass_rmse_guardrail = (
        rmse_ratio <= RMSE_RATIO_MAX if rmse_ratio is not None else None
    )
    pass_mae_guardrail = (
        mae_ratio <= MAE_RATIO_MAX if mae_ratio is not None else None
    )

    return SliceMetrics(
        n_samples=n_samples,
        n_valid=n_valid,
        n_skipped=n_skipped,
        n_error=n_error,
        n_r_updated=n_r_updated,
        n_r_skipped=n_r_skipped,
        n_adaptive_skipped=n_adaptive_skipped,
        latency_mean_ms=latency_mean_ms,
        latency_p95_ms=latency_p95_ms,
        rmse_arx=rmse_arx,
        mae_arx=mae_arx,
        rmse_filtered=rmse_filtered,
        mae_filtered=mae_filtered,
        var_diff_raw=var_diff_raw,
        var_diff_filtered=var_diff_filtered,
        variance_reduction=variance_reduction,
        rmse_ratio=rmse_ratio,
        mae_ratio=mae_ratio,
        innovation_mean=innovation_mean,
        innovation_std=innovation_std,
        innovation_max_abs=innovation_max_abs,
        R_mean=R_mean,
        R_min_observed=R_min_observed,
        R_max_observed=R_max_observed,
        P_mean=P_mean,
        P_max=P_max,
        pass_variance_reduction=pass_variance_reduction,
        pass_rmse_guardrail=pass_rmse_guardrail,
        pass_mae_guardrail=pass_mae_guardrail,
    )


# ── Helper nội bộ ─────────────────────────────────────────────────────────────


def _finite_values(rows: Sequence[dict], field: str) -> np.ndarray:
    """Trả về array float 1-D chỉ gồm giá trị hữu hạn của *field*.

    Dòng có field là ``None``, ``NaN`` hoặc ``Inf`` sẽ bị bỏ qua. Giá trị không
    phải số và không ép được sang ``float`` cũng bị bỏ qua.
    """
    out: list[float] = []
    for r in rows:
        v = r.get(field)
        if v is None:
            continue
        try:
            f = float(v)
        except (TypeError, ValueError):
            continue
        if np.isfinite(f):
            out.append(f)
    return np.array(out, dtype=float)


def _paired_values(
    rows: Sequence[dict],
    ref_key: str,
    pred_key: str,
) -> tuple[np.ndarray, np.ndarray]:
    """Trả về hai array song song khi CẢ HAI giá trị đều là float hữu hạn.

    Dòng mà một trong hai cột là ``None``, ``NaN``, ``Inf`` hoặc không phải số
    sẽ bị bỏ khỏi *cả hai* array. Vì vậy hai array trả về luôn cùng độ dài và
    dùng cùng index dòng.
    """
    refs, preds = [], []
    for r in rows:
        ref = r.get(ref_key)
        pred = r.get(pred_key)
        if ref is None or pred is None:
            continue
        try:
            f_ref, f_pred = float(ref), float(pred)
        except (TypeError, ValueError):
            continue
        if np.isfinite(f_ref) and np.isfinite(f_pred):
            refs.append(f_ref)
            preds.append(f_pred)
    return np.array(refs, dtype=float), np.array(preds, dtype=float)


def _rmse(refs: np.ndarray, preds: np.ndarray) -> float:
    return float(np.sqrt(np.mean((refs - preds) ** 2)))


def _mae(refs: np.ndarray, preds: np.ndarray) -> float:
    return float(np.mean(np.abs(refs - preds)))
