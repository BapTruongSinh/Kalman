"""
Pure evaluation metric computation.

Accepts plain dicts (from QuerySet.values()) so the computation layer
has no Django or DB dependency — it is unit-testable with synthetic data.

ADR-003 acceptance thresholds
------------------------------
variance_reduction  >= 0.20  (20 %)
rmse_ratio          <= 1.05
mae_ratio           <= 1.05
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

import numpy as np

# ── ADR-003 acceptance thresholds ─────────────────────────────────────────────
VARIANCE_REDUCTION_MIN: float = 0.20
RMSE_RATIO_MAX: float = 1.05
MAE_RATIO_MAX: float = 1.05


@dataclass(frozen=True)
class SliceMetrics:
    """All evaluation metrics for a single data slice (train / validation / test).

    Derived properties
    ------------------
    cycle_success_rate : n_valid / n_samples
    sample_loss_rate   : (n_skipped + n_error) / n_samples
    passes_acceptance_gate : True if all three ADR-003 flags are True
    """

    # ── Sample counts ──────────────────────────────────────────────────────────
    n_samples: int = 0
    n_valid: int = 0
    n_skipped: int = 0
    n_error: int = 0

    # ── Adaptive status distribution ───────────────────────────────────────────
    n_r_updated: int = 0
    n_r_skipped: int = 0
    n_adaptive_skipped: int = 0

    # ── Latency ────────────────────────────────────────────────────────────────
    latency_mean_ms: Optional[float] = None
    latency_p95_ms: Optional[float] = None

    # ── ARX accuracy (when arx_predicted & reference available) ───────────────
    rmse_arx: Optional[float] = None
    mae_arx: Optional[float] = None

    # ── Kalman accuracy (when kf_x_posterior & reference available) ───────────
    rmse_filtered: Optional[float] = None
    mae_filtered: Optional[float] = None

    # ── Variance reduction ────────────────────────────────────────────────────
    var_diff_raw: Optional[float] = None
    var_diff_filtered: Optional[float] = None
    variance_reduction: Optional[float] = None

    # ── Guardrail ratios ──────────────────────────────────────────────────────
    rmse_ratio: Optional[float] = None
    mae_ratio: Optional[float] = None

    # ── Innovation diagnostics ─────────────────────────────────────────────────
    innovation_mean: Optional[float] = None
    innovation_std: Optional[float] = None
    innovation_max_abs: Optional[float] = None

    # ── Adaptive R diagnostics ────────────────────────────────────────────────
    R_mean: Optional[float] = None
    R_min_observed: Optional[float] = None
    R_max_observed: Optional[float] = None

    # ── Posterior covariance ──────────────────────────────────────────────────
    P_mean: Optional[float] = None
    P_max: Optional[float] = None

    # ── ADR-003 pass / fail flags ─────────────────────────────────────────────
    pass_variance_reduction: Optional[bool] = None
    pass_rmse_guardrail: Optional[bool] = None
    pass_mae_guardrail: Optional[bool] = None

    # ── Derived properties ────────────────────────────────────────────────────

    @property
    def cycle_success_rate(self) -> Optional[float]:
        """Fraction of cycles that completed normally (n_valid / n_samples)."""
        if self.n_samples == 0:
            return None
        return self.n_valid / self.n_samples

    @property
    def sample_loss_rate(self) -> Optional[float]:
        """Fraction of samples lost to skips or errors."""
        if self.n_samples == 0:
            return None
        return (self.n_skipped + self.n_error) / self.n_samples

    @property
    def passes_acceptance_gate(self) -> bool:
        """True iff all three ADR-003 acceptance criteria pass."""
        return bool(
            self.pass_variance_reduction
            and self.pass_rmse_guardrail
            and self.pass_mae_guardrail
        )


# ── Computation ────────────────────────────────────────────────────────────────


def compute_metrics(rows: Sequence[dict]) -> SliceMetrics:
    """Compute all evaluation metrics from a sequence of cycle-row dicts.

    Parameters
    ----------
    rows:
        Dicts produced by ``PipelineCycle.objects.values(...)``.
        Expected keys (all optional / nullable):
        ``raw_soil_moisture``, ``arx_predicted``, ``kf_x_prior``,
        ``kf_P_prior``, ``kf_innovation``, ``kf_R``, ``kf_K``,
        ``kf_x_posterior``, ``kf_P_posterior``,
        ``cycle_status``, ``adaptive_status``, ``latency_ms``.

    Returns
    -------
    SliceMetrics
        Immutable dataclass with every computed metric.  Fields are ``None``
        when there is insufficient data (e.g. no ARX predictions available).
    """
    if not rows:
        return SliceMetrics()

    n_samples = len(rows)
    n_valid = sum(1 for r in rows if r.get("cycle_status") == "ok")
    n_skipped = sum(
        1 for r in rows if r.get("cycle_status", "").startswith("skipped")
    )
    n_error = sum(1 for r in rows if r.get("cycle_status") == "error")

    # ── Adaptive status distribution ──────────────────────────────────────────
    n_r_updated = sum(1 for r in rows if r.get("adaptive_status") == "R_updated")
    n_r_skipped = sum(1 for r in rows if r.get("adaptive_status") == "R_skipped")
    n_adaptive_skipped = sum(1 for r in rows if r.get("adaptive_status") == "skipped")

    # ── Latency ───────────────────────────────────────────────────────────────
    latencies = [r["latency_ms"] for r in rows if r.get("latency_ms") is not None]
    if latencies:
        lat_arr = np.array(latencies, dtype=float)
        latency_mean_ms = float(np.mean(lat_arr))
        latency_p95_ms = float(np.percentile(lat_arr, 95))
    else:
        latency_mean_ms = latency_p95_ms = None

    # ── Accuracy metrics (ok cycles with reference available) ─────────────────
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

    # ── Variance reduction ────────────────────────────────────────────────────
    raw_vals = np.array(
        [r["raw_soil_moisture"] for r in rows if r.get("raw_soil_moisture") is not None],
        dtype=float,
    )
    filt_vals = np.array(
        [r["kf_x_posterior"] for r in rows if r.get("kf_x_posterior") is not None],
        dtype=float,
    )

    var_diff_raw = float(np.var(np.diff(raw_vals))) if len(raw_vals) >= 2 else None
    var_diff_filtered = float(np.var(np.diff(filt_vals))) if len(filt_vals) >= 2 else None

    if var_diff_raw is not None and var_diff_raw > 0 and var_diff_filtered is not None:
        variance_reduction = 1.0 - (var_diff_filtered / var_diff_raw)
    else:
        variance_reduction = None

    # ── Guardrail ratios ──────────────────────────────────────────────────────
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

    # ── Innovation diagnostics ────────────────────────────────────────────────
    innovations = np.array(
        [r["kf_innovation"] for r in rows if r.get("kf_innovation") is not None],
        dtype=float,
    )
    if len(innovations) > 0:
        innovation_mean = float(np.mean(innovations))
        innovation_std = float(np.std(innovations))
        innovation_max_abs = float(np.max(np.abs(innovations)))
    else:
        innovation_mean = innovation_std = innovation_max_abs = None

    # ── Adaptive R diagnostics ────────────────────────────────────────────────
    r_vals = np.array(
        [r["kf_R"] for r in rows if r.get("kf_R") is not None],
        dtype=float,
    )
    if len(r_vals) > 0:
        R_mean = float(np.mean(r_vals))
        R_min_observed = float(np.min(r_vals))
        R_max_observed = float(np.max(r_vals))
    else:
        R_mean = R_min_observed = R_max_observed = None

    # ── Posterior covariance ──────────────────────────────────────────────────
    p_vals = np.array(
        [r["kf_P_posterior"] for r in rows if r.get("kf_P_posterior") is not None],
        dtype=float,
    )
    if len(p_vals) > 0:
        P_mean = float(np.mean(p_vals))
        P_max = float(np.max(p_vals))
    else:
        P_mean = P_max = None

    # ── ADR-003 pass / fail ───────────────────────────────────────────────────
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


# ── Private helpers ────────────────────────────────────────────────────────────


def _paired_values(
    rows: list[dict],
    ref_key: str,
    pred_key: str,
) -> tuple[np.ndarray, np.ndarray]:
    """Return parallel arrays for pairs where both values are non-None finite floats."""
    refs, preds = [], []
    for r in rows:
        ref = r.get(ref_key)
        pred = r.get(pred_key)
        if ref is not None and pred is not None:
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
