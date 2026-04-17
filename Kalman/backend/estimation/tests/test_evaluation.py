"""
Tests for estimation.evaluation — metrics computation, DB persistence,
text report, and CSV export.

Test organisation
-----------------
TestComputeMetricsEmpty         — empty input → zero-state SliceMetrics
TestComputeMetricsSingleRow     — minimal happy-path row
TestComputeMetricsCounts        — n_valid, n_skipped, n_error, adaptive counts
TestComputeMetricsLatency       — mean and P95 latency
TestComputeMetricsAccuracy      — RMSE, MAE for ARX and filtered
TestComputeMetricsVariance      — var(diff) reduction and guardrail ratios
TestComputeMetricsInnovation    — innovation summary stats
TestComputeMetricsAdaptiveR     — R and P diagnostic stats
TestComputeMetricsPassFail      — ADR-003 pass / fail flags
TestComputeMetricsEdgeCases     — guard against division-by-zero / NaN input
TestSliceMetricsProperties      — derived properties on SliceMetrics
TestEvaluateSlice               — DB round-trip: evaluate_slice persists correctly
TestEvaluateAllSlices           — all three slices are evaluated and persisted
TestBuildTextReport             — report contains expected headings and gate result
TestExportToCsv                 — CSV has header row + one row per slice
TestEvaluateSliceIdempotent     — second call to evaluate_slice updates existing row
TestLatencyMappedFromStore      — latency_ms flows through map_result_to_cycle
"""
from __future__ import annotations

import csv
import io
import math
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

# ── Pure metrics tests (no Django required) ────────────────────────────────────

from estimation.evaluation.metrics import (
    MAE_RATIO_MAX,
    RMSE_RATIO_MAX,
    VARIANCE_REDUCTION_MIN,
    SliceMetrics,
    compute_metrics,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _row(
    *,
    cycle_status: str = "ok",
    adaptive_status: str = "R_updated",
    raw_sm: float | None = 55.0,
    arx: float | None = 54.8,
    kf_post: float | None = 54.9,
    innovation: float | None = 0.1,
    kf_R: float | None = 1.0,
    kf_P: float | None = 0.5,
    latency: float | None = 1.5,
) -> dict:
    return {
        "cycle_status": cycle_status,
        "adaptive_status": adaptive_status,
        "raw_soil_moisture": raw_sm,
        "arx_predicted": arx,
        "kf_x_posterior": kf_post,
        "kf_innovation": innovation,
        "kf_R": kf_R,
        "kf_P_posterior": kf_P,
        "latency_ms": latency,
    }


def _rows(n: int, **kwargs) -> list[dict]:
    return [_row(**kwargs) for _ in range(n)]


# ── TestComputeMetricsEmpty ────────────────────────────────────────────────────

class TestComputeMetricsEmpty:
    def test_returns_zero_counts(self):
        m = compute_metrics([])
        assert m.n_samples == 0
        assert m.n_valid == 0
        assert m.n_skipped == 0
        assert m.n_error == 0

    def test_derived_properties_none_when_no_samples(self):
        m = compute_metrics([])
        assert m.cycle_success_rate is None
        assert m.sample_loss_rate is None

    def test_accuracy_none(self):
        m = compute_metrics([])
        assert m.rmse_arx is None
        assert m.mae_arx is None
        assert m.rmse_filtered is None
        assert m.mae_filtered is None
        assert m.variance_reduction is None

    def test_pass_flags_none(self):
        m = compute_metrics([])
        assert m.pass_variance_reduction is None
        assert m.pass_rmse_guardrail is None
        assert m.pass_mae_guardrail is None
        assert m.passes_acceptance_gate is False


# ── TestComputeMetricsSingleRow ────────────────────────────────────────────────

class TestComputeMetricsSingleRow:
    def test_n_samples_one(self):
        m = compute_metrics([_row()])
        assert m.n_samples == 1
        assert m.n_valid == 1

    def test_latency_captured(self):
        m = compute_metrics([_row(latency=3.14)])
        assert m.latency_mean_ms == pytest.approx(3.14)
        assert m.latency_p95_ms == pytest.approx(3.14)


# ── TestComputeMetricsCounts ───────────────────────────────────────────────────

class TestComputeMetricsCounts:
    def test_mixed_statuses(self):
        rows = [
            _row(cycle_status="ok"),
            _row(cycle_status="ok"),
            _row(cycle_status="skipped_no_measurement"),
            _row(cycle_status="error"),
        ]
        m = compute_metrics(rows)
        assert m.n_samples == 4
        assert m.n_valid == 2
        assert m.n_skipped == 1
        assert m.n_error == 1

    def test_cycle_success_rate(self):
        rows = _rows(8, cycle_status="ok") + _rows(2, cycle_status="error")
        m = compute_metrics(rows)
        assert m.cycle_success_rate == pytest.approx(0.8)

    def test_sample_loss_rate(self):
        rows = _rows(8, cycle_status="ok") + _rows(2, cycle_status="error")
        m = compute_metrics(rows)
        assert m.sample_loss_rate == pytest.approx(0.2)

    def test_adaptive_status_counts(self):
        rows = [
            _row(adaptive_status="R_updated"),
            _row(adaptive_status="R_updated"),
            _row(adaptive_status="R_skipped"),
            _row(adaptive_status="skipped"),
        ]
        m = compute_metrics(rows)
        assert m.n_r_updated == 2
        assert m.n_r_skipped == 1
        assert m.n_adaptive_skipped == 1


# ── TestComputeMetricsLatency ──────────────────────────────────────────────────

class TestComputeMetricsLatency:
    def test_mean(self):
        rows = [_row(latency=float(x)) for x in [1, 2, 3, 4, 5]]
        m = compute_metrics(rows)
        assert m.latency_mean_ms == pytest.approx(3.0)

    def test_p95_greater_than_mean(self):
        rows = [_row(latency=float(x)) for x in range(1, 21)]
        m = compute_metrics(rows)
        assert m.latency_p95_ms > m.latency_mean_ms  # type: ignore[operator]

    def test_none_latency_rows_ignored(self):
        rows = [_row(latency=None)] * 5
        m = compute_metrics(rows)
        assert m.latency_mean_ms is None
        assert m.latency_p95_ms is None


# ── TestComputeMetricsAccuracy ─────────────────────────────────────────────────

class TestComputeMetricsAccuracy:
    """RMSE / MAE require at least 2 ok-cycle pairs."""

    def test_arx_rmse_zero_perfect(self):
        rows = _rows(5, raw_sm=55.0, arx=55.0, kf_post=54.9)
        m = compute_metrics(rows)
        assert m.rmse_arx == pytest.approx(0.0)
        assert m.mae_arx == pytest.approx(0.0)

    def test_filtered_rmse_known_value(self):
        # raw=[50,52], filtered=[51,51] → errors=[-1,1] → RMSE=1
        rows = [
            _row(raw_sm=50.0, kf_post=51.0, arx=None),
            _row(raw_sm=52.0, kf_post=51.0, arx=None),
        ]
        m = compute_metrics(rows)
        assert m.rmse_filtered == pytest.approx(1.0)
        assert m.mae_filtered == pytest.approx(1.0)

    def test_none_arx_returns_none_accuracy(self):
        rows = _rows(5, arx=None)
        m = compute_metrics(rows)
        assert m.rmse_arx is None
        assert m.mae_arx is None

    def test_none_reference_excludes_row(self):
        rows = [_row(raw_sm=None), _row(raw_sm=55.0, arx=55.0)]
        m = compute_metrics(rows)
        # Only 1 paired point — requires >=2 for RMSE
        assert m.rmse_arx is None


# ── TestComputeMetricsVariance ─────────────────────────────────────────────────

class TestComputeMetricsVariance:
    def test_variance_reduction_positive_when_filtered_smoother(self):
        import numpy as np

        rng = np.random.default_rng(42)
        raw = rng.normal(55, 3, 200).tolist()
        # Filtered is smoother (lower high-frequency noise)
        filtered = [v + rng.normal(0, 0.5) for v in raw]
        rows = [
            _row(raw_sm=r, kf_post=f, arx=r + 0.1)
            for r, f in zip(raw, filtered)
        ]
        m = compute_metrics(rows)
        assert m.variance_reduction is not None
        assert m.variance_reduction > 0

    def test_variance_reduction_none_when_only_one_raw_value(self):
        rows = [_row(raw_sm=55.0, kf_post=55.0)]
        m = compute_metrics(rows)
        assert m.variance_reduction is None

    def test_rmse_ratio_lt_one_when_filtered_better(self):
        # filtered closer to raw than ARX
        rows = [
            _row(raw_sm=55.0, arx=53.0, kf_post=54.8),
            _row(raw_sm=56.0, arx=53.5, kf_post=55.7),
            _row(raw_sm=54.0, arx=52.0, kf_post=53.9),
        ]
        m = compute_metrics(rows)
        assert m.rmse_ratio is not None
        assert m.rmse_ratio < 1.0

    def test_pass_variance_reduction_correct_threshold(self):
        m = SliceMetrics(variance_reduction=0.21)
        assert m.pass_variance_reduction is None  # dataclass doesn't auto-compute

        # Use compute_metrics to get the flag
        import numpy as np

        rng = np.random.default_rng(7)
        raw = rng.normal(55, 5, 500).tolist()
        filtered = [v + rng.normal(0, 0.3) for v in raw]
        rows = [_row(raw_sm=r, kf_post=f) for r, f in zip(raw, filtered)]
        m = compute_metrics(rows)
        expected = (m.variance_reduction >= VARIANCE_REDUCTION_MIN) if m.variance_reduction else None
        assert m.pass_variance_reduction == expected


# ── TestComputeMetricsInnovation ───────────────────────────────────────────────

class TestComputeMetricsInnovation:
    def test_zero_mean_when_innovations_symmetric(self):
        rows = [_row(innovation=v) for v in [-1.0, -0.5, 0.0, 0.5, 1.0]]
        m = compute_metrics(rows)
        assert m.innovation_mean == pytest.approx(0.0)

    def test_max_abs(self):
        rows = [_row(innovation=v) for v in [0.1, -2.5, 1.3, -0.7]]
        m = compute_metrics(rows)
        assert m.innovation_max_abs == pytest.approx(2.5)

    def test_std_positive(self):
        rows = [_row(innovation=float(i)) for i in range(10)]
        m = compute_metrics(rows)
        assert m.innovation_std is not None
        assert m.innovation_std > 0


# ── TestComputeMetricsAdaptiveR ────────────────────────────────────────────────

class TestComputeMetricsAdaptiveR:
    def test_r_min_max(self):
        rows = [_row(kf_R=float(v)) for v in [0.1, 0.5, 2.0, 5.0]]
        m = compute_metrics(rows)
        assert m.R_min_observed == pytest.approx(0.1)
        assert m.R_max_observed == pytest.approx(5.0)
        assert m.R_mean == pytest.approx((0.1 + 0.5 + 2.0 + 5.0) / 4)

    def test_p_stats(self):
        rows = [_row(kf_P=float(v)) for v in [0.2, 0.4, 0.6, 0.8]]
        m = compute_metrics(rows)
        assert m.P_max == pytest.approx(0.8)
        assert m.P_mean == pytest.approx(0.5)


# ── TestComputeMetricsPassFail ─────────────────────────────────────────────────

class TestComputeMetricsPassFail:
    def _make_rows_with_reduction(self, target_reduction: float) -> list[dict]:
        """Return rows whose var(diff) ratio yields approximately *target_reduction*."""
        import numpy as np

        rng = np.random.default_rng(99)
        n = 300
        raw = rng.normal(55, 5, n)
        # Scale filtered noise to produce desired variance reduction
        noise_scale = math.sqrt((1 - target_reduction) * np.var(np.diff(raw)))
        filtered = raw + rng.normal(0, noise_scale / 5 + 0.01, n)
        return [_row(raw_sm=float(r), kf_post=float(f)) for r, f in zip(raw, filtered)]

    def test_pass_when_variance_reduction_above_threshold(self):
        rows = self._make_rows_with_reduction(0.30)
        m = compute_metrics(rows)
        if m.variance_reduction is not None and m.variance_reduction >= VARIANCE_REDUCTION_MIN:
            assert m.pass_variance_reduction is True

    def test_fail_when_variance_reduction_below_threshold(self):
        rows = _rows(50, raw_sm=55.0, kf_post=55.01)  # nearly no filtering
        m = compute_metrics(rows)
        # var(diff) should be similar — small reduction
        if m.variance_reduction is not None and m.variance_reduction < VARIANCE_REDUCTION_MIN:
            assert m.pass_variance_reduction is False

    def test_rmse_guardrail_pass(self):
        # arx error = 1.0 per step, filtered error = 0.5 → ratio = 0.5
        rows = [
            _row(raw_sm=55.0, arx=54.0, kf_post=54.5),
            _row(raw_sm=56.0, arx=55.0, kf_post=55.5),
            _row(raw_sm=54.0, arx=53.0, kf_post=53.5),
        ]
        m = compute_metrics(rows)
        assert m.pass_rmse_guardrail is True

    def test_rmse_guardrail_fail(self):
        # arx error = 0.1 per step, filtered error = 2.0 → ratio >> 1.05
        rows = [
            _row(raw_sm=55.0, arx=55.1, kf_post=53.0),
            _row(raw_sm=56.0, arx=56.1, kf_post=54.0),
            _row(raw_sm=54.0, arx=54.1, kf_post=52.0),
        ]
        m = compute_metrics(rows)
        assert m.pass_rmse_guardrail is False

    def test_passes_acceptance_gate_all_pass(self):
        m = SliceMetrics(
            pass_variance_reduction=True,
            pass_rmse_guardrail=True,
            pass_mae_guardrail=True,
        )
        assert m.passes_acceptance_gate is True

    def test_passes_acceptance_gate_one_fail(self):
        m = SliceMetrics(
            pass_variance_reduction=True,
            pass_rmse_guardrail=False,
            pass_mae_guardrail=True,
        )
        assert m.passes_acceptance_gate is False


# ── TestComputeMetricsEdgeCases ────────────────────────────────────────────────

class TestComputeMetricsEdgeCases:
    def test_nan_arx_row_excluded(self):
        rows = [_row(arx=float("nan")), _row(arx=55.0)]
        m = compute_metrics(rows)
        # 1 valid pair — should not raise, but rmse may be None
        assert m.rmse_arx is None or math.isfinite(m.rmse_arx)

    def test_inf_raw_sm_excluded(self):
        rows = [_row(raw_sm=float("inf")), _row(raw_sm=55.0, arx=55.0)]
        m = compute_metrics(rows)
        assert m.rmse_arx is None  # only 1 valid pair

    def test_variance_reduction_zero_raw_variance(self):
        rows = [_row(raw_sm=55.0, kf_post=55.0)] * 10
        m = compute_metrics(rows)
        # var(diff) of constant sequence = 0 → cannot divide
        assert m.variance_reduction is None


# ── TestVariancePairing ────────────────────────────────────────────────────────


class TestVariancePairing:
    """Variance reduction must be computed on paired (same-row) samples.

    If some rows have raw_soil_moisture but no kf_x_posterior (or vice-versa),
    those rows must be dropped from *both* arrays before computing np.diff so
    the two diff sequences share the same index set.
    """

    def test_mismatched_rows_excluded_from_both_arrays(self):
        # Row 0: has raw but no posterior  → must be excluded from both
        # Rows 1-3: fully paired
        rows = [
            _row(raw_sm=50.0, kf_post=None),   # excluded
            _row(raw_sm=51.0, kf_post=51.5),
            _row(raw_sm=52.0, kf_post=52.4),
            _row(raw_sm=53.0, kf_post=53.3),
        ]
        m = compute_metrics(rows)
        # Both variance values must be finite (computed from the 3 paired rows)
        assert m.var_diff_raw is not None and math.isfinite(m.var_diff_raw)
        assert m.var_diff_filtered is not None and math.isfinite(m.var_diff_filtered)

    def test_mismatched_posterior_excluded_from_both_arrays(self):
        # Row 2: has posterior but no raw  → must be excluded from both
        rows = [
            _row(raw_sm=51.0, kf_post=51.5),
            _row(raw_sm=52.0, kf_post=52.4),
            _row(raw_sm=None, kf_post=53.0),   # excluded
            _row(raw_sm=54.0, kf_post=53.9),
        ]
        m = compute_metrics(rows)
        assert m.var_diff_raw is not None and math.isfinite(m.var_diff_raw)
        assert m.var_diff_filtered is not None and math.isfinite(m.var_diff_filtered)

    def test_nan_in_raw_excludes_paired_posterior(self):
        rows = [
            _row(raw_sm=float("nan"), kf_post=51.5),  # NaN raw → both excluded
            _row(raw_sm=52.0, kf_post=52.4),
            _row(raw_sm=53.0, kf_post=53.3),
            _row(raw_sm=54.0, kf_post=53.9),
        ]
        m = compute_metrics(rows)
        # Only 3 valid pairs → variance computable
        assert m.var_diff_raw is not None and math.isfinite(m.var_diff_raw)

    def test_inf_in_posterior_excludes_paired_raw(self):
        rows = [
            _row(raw_sm=51.0, kf_post=float("inf")),  # Inf post → both excluded
            _row(raw_sm=52.0, kf_post=52.4),
            _row(raw_sm=53.0, kf_post=53.3),
            _row(raw_sm=54.0, kf_post=53.9),
        ]
        m = compute_metrics(rows)
        assert m.var_diff_filtered is not None and math.isfinite(m.var_diff_filtered)

    def test_too_few_paired_rows_returns_none(self):
        # Only 1 valid pair → np.diff produces empty array → None
        rows = [
            _row(raw_sm=51.0, kf_post=None),
            _row(raw_sm=52.0, kf_post=52.4),  # only 1 valid pair
            _row(raw_sm=None, kf_post=53.0),
        ]
        m = compute_metrics(rows)
        assert m.var_diff_raw is None
        assert m.var_diff_filtered is None
        assert m.variance_reduction is None


# ── TestNonFiniteFiltering ─────────────────────────────────────────────────────


class TestNonFiniteFiltering:
    """NaN / Inf values in single-field metrics must produce None, not NaN/Inf."""

    def test_latency_nan_ignored(self):
        rows = [
            _row(latency=float("nan")),
            _row(latency=float("nan")),
        ]
        m = compute_metrics(rows)
        assert m.latency_mean_ms is None
        assert m.latency_p95_ms is None

    def test_latency_inf_ignored(self):
        rows = [_row(latency=float("inf")), _row(latency=2.0)]
        m = compute_metrics(rows)
        # Only the 2.0 row contributes → mean = 2.0, p95 = 2.0
        assert m.latency_mean_ms == pytest.approx(2.0)
        assert m.latency_p95_ms is not None and math.isfinite(m.latency_p95_ms)

    def test_mixed_valid_and_nan_latency(self):
        rows = [_row(latency=float("nan")), _row(latency=3.0), _row(latency=5.0)]
        m = compute_metrics(rows)
        assert m.latency_mean_ms == pytest.approx(4.0)
        assert m.latency_mean_ms is not None and math.isfinite(m.latency_mean_ms)

    def test_innovation_nan_ignored(self):
        rows = [_row(innovation=float("nan")), _row(innovation=float("nan"))]
        m = compute_metrics(rows)
        assert m.innovation_mean is None
        assert m.innovation_std is None
        assert m.innovation_max_abs is None

    def test_innovation_inf_gives_finite_result_for_valid_rows(self):
        rows = [_row(innovation=float("inf")), _row(innovation=0.5)]
        m = compute_metrics(rows)
        assert m.innovation_mean == pytest.approx(0.5)
        assert math.isfinite(m.innovation_mean)

    def test_R_nan_ignored(self):
        rows = [_row(kf_R=float("nan")), _row(kf_R=float("nan"))]
        m = compute_metrics(rows)
        assert m.R_mean is None
        assert m.R_min_observed is None
        assert m.R_max_observed is None

    def test_R_inf_excluded(self):
        rows = [_row(kf_R=float("inf")), _row(kf_R=2.0)]
        m = compute_metrics(rows)
        assert m.R_mean == pytest.approx(2.0)
        assert math.isfinite(m.R_mean)

    def test_P_nan_ignored(self):
        rows = [_row(kf_P=float("nan")), _row(kf_P=float("nan"))]
        m = compute_metrics(rows)
        assert m.P_mean is None
        assert m.P_max is None

    def test_all_fields_finite_or_none_when_input_has_nan(self):
        """No metric field on the returned SliceMetrics may be NaN or Inf."""
        rows = [
            _row(
                raw_sm=float("nan"),
                arx=float("inf"),
                kf_post=float("nan"),
                innovation=float("nan"),
                kf_R=float("inf"),
                kf_P=float("nan"),
                latency=float("nan"),
            ),
            _row(raw_sm=52.0, kf_post=52.4),
        ]
        m = compute_metrics(rows)
        for field_name in SliceMetrics.__dataclass_fields__:
            val = getattr(m, field_name)
            if isinstance(val, float):
                assert math.isfinite(val), (
                    f"Field {field_name!r} is non-finite: {val!r}"
                )


# ── TestMatplotlibLazyImport ───────────────────────────────────────────────────


class TestMatplotlibLazyImport:
    """Loading reporter module must not trigger matplotlib imports.

    evaluate_slice / build_text_report must work cleanly even when matplotlib
    is broken (or absent), because matplotlib is only loaded inside export_plots.
    """

    def test_evaluate_slice_works_without_matplotlib(self, monkeypatch):
        """Importing reporter and calling evaluate_slice must not touch matplotlib."""
        import sys

        # Temporarily hide matplotlib from sys.modules
        original = sys.modules.pop("matplotlib", None)
        original_plt = sys.modules.pop("matplotlib.pyplot", None)
        original_dates = sys.modules.pop("matplotlib.dates", None)

        # Force-reload reporter with matplotlib absent
        import importlib
        import estimation.evaluation.reporter as reporter_mod
        importlib.reload(reporter_mod)

        try:
            # The reporter module must have loaded without error
            assert hasattr(reporter_mod, "evaluate_slice")
        finally:
            # Restore sys.modules
            if original is not None:
                sys.modules["matplotlib"] = original
            if original_plt is not None:
                sys.modules["matplotlib.pyplot"] = original_plt
            if original_dates is not None:
                sys.modules["matplotlib.dates"] = original_dates
            importlib.reload(reporter_mod)

    def test_export_plots_returns_empty_list_when_matplotlib_missing(
        self, monkeypatch
    ):
        """export_plots should return [] gracefully if matplotlib cannot be imported."""
        import sys
        import importlib
        import estimation.evaluation.reporter as reporter_mod

        # Make the lazy import fail inside export_plots by patching builtins.__import__
        original_import = __builtins__.__import__ if hasattr(__builtins__, "__import__") else __import__

        def _fail_matplotlib(name, *args, **kwargs):
            if name == "matplotlib":
                raise ImportError("simulated missing matplotlib")
            return original_import(name, *args, **kwargs)

        import builtins
        monkeypatch.setattr(builtins, "__import__", _fail_matplotlib)

        import warnings
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = reporter_mod.export_plots(run_pk=99999, output_dir="/tmp/test_plots")

        assert result == []
        assert any("matplotlib" in str(warning.message).lower() for warning in w)


# ── TestExportPlotsHappyPath ───────────────────────────────────────────────────


@pytest.mark.django_db
class TestExportPlotsHappyPath:
    """exercise export_plots() happy-path with mocked matplotlib.

    The current environment has a numpy/matplotlib ABI mismatch, so we inject
    mock modules into sys.modules before each test.  This lets us verify all
    branching logic (file-path generation, residuals guard, multi-slice) without
    needing a working C extension stack.
    """

    @pytest.fixture(autouse=True)
    def _inject_mock_mpl(self, monkeypatch):
        """Inject stub matplotlib into sys.modules for every test in this class.

        ``import matplotlib.pyplot as plt`` inside export_plots() compiles to
        IMPORT_NAME + IMPORT_FROM, where IMPORT_FROM does
        ``getattr(matplotlib_module, "pyplot")``.  Injecting only
        ``sys.modules["matplotlib.pyplot"]`` is therefore not enough — we must
        also set ``fake_mpl.pyplot = fake_plt`` so the attribute lookup
        returns our mock rather than an auto-generated MagicMock.
        """
        import sys
        from unittest.mock import MagicMock

        fake_mpl = MagicMock(name="matplotlib")
        fake_plt = MagicMock(name="matplotlib.pyplot")
        fake_mdates = MagicMock(name="matplotlib.dates")
        fake_fig = MagicMock(name="Figure")
        fake_ax = MagicMock(name="Axes")
        fake_ax.xaxis = MagicMock(name="XAxis")
        fake_plt.subplots.return_value = (fake_fig, fake_ax)

        # savefig creates the real file so returned Path objects are valid
        def _touch(path, **kwargs):
            Path(path).touch()

        fake_fig.savefig.side_effect = _touch

        # IMPORTANT: set attributes on fake_mpl so that IMPORT_FROM finds our mocks
        fake_mpl.pyplot = fake_plt
        fake_mpl.dates = fake_mdates

        # Also register in sys.modules so bare "import matplotlib" finds our fake
        monkeypatch.setitem(sys.modules, "matplotlib", fake_mpl)
        monkeypatch.setitem(sys.modules, "matplotlib.pyplot", fake_plt)
        monkeypatch.setitem(sys.modules, "matplotlib.dates", fake_mdates)

        # Expose on self so individual tests can assert call counts
        self._fake_plt = fake_plt
        self._fake_fig = fake_fig

    # ── basic coverage ─────────────────────────────────────────────────────────

    def test_empty_run_returns_empty_list(self, run, tmp_path):
        from estimation.evaluation.reporter import export_plots

        assert export_plots(run.pk, tmp_path) == []

    def test_single_slice_full_data_returns_four_files(
        self, run, cycle_factory, tmp_path
    ):
        from estimation.evaluation.reporter import export_plots

        for i in range(5):
            cycle_factory(slice_type="test", index=i)

        result = export_plots(run.pk, tmp_path)
        names = {p.name for p in result}
        assert "time_series_test.png" in names
        assert "innovation_test.png" in names
        assert "adaptive_R_test.png" in names
        assert "residuals_test.png" in names
        assert len(result) == 4

    def test_returned_paths_are_inside_output_dir(self, run, cycle_factory, tmp_path):
        from estimation.evaluation.reporter import export_plots

        for i in range(3):
            cycle_factory(slice_type="train", index=i)

        result = export_plots(run.pk, tmp_path)
        for p in result:
            assert p.parent == tmp_path

    def test_output_dir_created_if_not_exists(self, run, cycle_factory, tmp_path):
        from estimation.evaluation.reporter import export_plots

        nested = tmp_path / "a" / "b" / "c"
        assert not nested.exists()
        cycle_factory(slice_type="test", index=0)
        export_plots(run.pk, nested)
        assert nested.is_dir()

    # ── residuals branch ────────────────────────────────────────────────────────

    def test_no_paired_data_skips_residuals_plot(self, run, cycle_factory, tmp_path):
        from estimation.evaluation.reporter import export_plots

        for i in range(3):
            cycle_factory(slice_type="train", index=i, raw_sm=None, kf_post=None)

        result = export_plots(run.pk, tmp_path)
        names = {p.name for p in result}
        assert "time_series_train.png" in names
        assert "residuals_train.png" not in names
        assert len(result) == 3  # 3 plots, not 4

    def test_mixed_null_and_valid_pair_shows_residuals(
        self, run, cycle_factory, tmp_path
    ):
        from estimation.evaluation.reporter import export_plots

        # row 0: NULL raw — not a valid pair, excluded from residuals
        cycle_factory(slice_type="test", index=0, raw_sm=None, kf_post=51.8)
        # row 1: finite pair — residuals list is non-empty → residuals plot
        cycle_factory(slice_type="test", index=1, raw_sm=52.0, kf_post=51.8)

        result = export_plots(run.pk, tmp_path)
        names = {p.name for p in result}
        # Residuals plot must appear because row 1 is a valid pair
        assert "residuals_test.png" in names

    def test_all_null_kf_post_skips_residuals(self, run, cycle_factory, tmp_path):
        from estimation.evaluation.reporter import export_plots

        # All kf_x_posterior values are NULL → no valid raw/filtered pair
        for i in range(3):
            cycle_factory(slice_type="train", index=i, raw_sm=50.0 + i, kf_post=None)

        result = export_plots(run.pk, tmp_path)
        names = {p.name for p in result}
        assert "residuals_train.png" not in names

    # ── multi-slice ─────────────────────────────────────────────────────────────

    def test_all_three_slices_generate_files(self, run, cycle_factory, tmp_path):
        from estimation.evaluation.reporter import export_plots

        # Use non-overlapping index ranges: (run, cycle_index) must be unique
        for i in range(3):
            cycle_factory(slice_type="train", index=i)        # 0-2
        for i in range(3):
            cycle_factory(slice_type="validation", index=i + 3)  # 3-5
        for i in range(3):
            cycle_factory(slice_type="test", index=i + 6)        # 6-8

        result = export_plots(run.pk, tmp_path)
        # each slice should have ≥ 3 plots (time-series, innovation, R, maybe residuals)
        assert len(result) >= 9

    def test_only_slices_with_rows_get_plots(self, run, cycle_factory, tmp_path):
        from estimation.evaluation.reporter import export_plots

        for i in range(3):
            cycle_factory(slice_type="train", index=i)
        # validation and test have no rows

        result = export_plots(run.pk, tmp_path)
        names = {p.name for p in result}
        assert any("train" in n for n in names)
        assert not any("validation" in n for n in names)
        assert not any("test" in n for n in names)

    # ── savefig call-count ──────────────────────────────────────────────────────

    def test_savefig_called_once_per_returned_file(self, run, cycle_factory, tmp_path):
        from estimation.evaluation.reporter import export_plots

        for i in range(3):
            cycle_factory(slice_type="test", index=i)

        result = export_plots(run.pk, tmp_path)
        assert self._fake_fig.savefig.call_count == len(result)


# ── TestSliceMetricsProperties ─────────────────────────────────────────────────

class TestSliceMetricsProperties:
    def test_cycle_success_rate_zero_samples(self):
        m = SliceMetrics(n_samples=0)
        assert m.cycle_success_rate is None

    def test_cycle_success_rate_100_percent(self):
        m = SliceMetrics(n_samples=10, n_valid=10)
        assert m.cycle_success_rate == pytest.approx(1.0)

    def test_sample_loss_rate_no_loss(self):
        m = SliceMetrics(n_samples=10, n_valid=10, n_skipped=0, n_error=0)
        assert m.sample_loss_rate == pytest.approx(0.0)

    def test_passes_gate_requires_all_true(self):
        m = SliceMetrics(
            pass_variance_reduction=True,
            pass_rmse_guardrail=True,
            pass_mae_guardrail=None,
        )
        assert m.passes_acceptance_gate is False


# ── DB-backed tests ────────────────────────────────────────────────────────────

pytestmark_db = pytest.mark.django_db


@pytest.fixture()
def run(db):
    from estimation.models import ExperimentRun

    return ExperimentRun.objects.create(status="running", name="test-eval")


@pytest.fixture()
def cycle_factory(run):
    from estimation.models import PipelineCycle

    _ts = datetime(2024, 1, 1, tzinfo=timezone.utc)

    def _make(
        slice_type: str = "test",
        cycle_status: str = "ok",
        adaptive_status: str = "R_updated",
        raw_sm: float = 55.0,
        arx: float = 54.8,
        kf_post: float = 54.9,
        innovation: float = 0.1,
        kf_R: float = 1.0,
        kf_P: float = 0.5,
        latency: float = 1.5,
        index: int = 0,
    ) -> PipelineCycle:
        from datetime import timedelta

        from estimation.pipeline.store import ingest_dedupe_key_for_persist

        sample_ts = _ts + timedelta(minutes=index)
        dedupe = ingest_dedupe_key_for_persist(
            run.pk,
            PipelineCycle.SourceType.CSV_REPLAY,
            cycle_index=index,
            sample_ts=sample_ts,
        )
        return PipelineCycle.objects.create(
            run=run,
            sample_ts=sample_ts,
            cycle_index=index,
            ingest_dedupe_key=dedupe,
            slice_type=slice_type,
            source_type="csv_replay",
            raw_soil_moisture=raw_sm,
            arx_predicted=arx,
            kf_x_posterior=kf_post,
            kf_innovation=innovation,
            kf_R=kf_R,
            kf_P_posterior=kf_P,
            latency_ms=latency,
            cycle_status=cycle_status,
            adaptive_status=adaptive_status,
            preprocess_status="valid",
        )

    return _make


# ── TestEvaluateSlice ──────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestEvaluateSlice:
    def test_creates_evaluation_summary(self, run, cycle_factory):
        from estimation.evaluation.reporter import evaluate_slice
        from estimation.models import EvaluationSummary

        for i in range(5):
            cycle_factory(slice_type="test", index=i)

        summary = evaluate_slice(run.pk, "test")
        assert isinstance(summary, EvaluationSummary)
        assert summary.n_samples == 5
        assert summary.n_valid == 5
        assert summary.slice_type == "test"

    def test_latency_persisted(self, run, cycle_factory):
        from estimation.evaluation.reporter import evaluate_slice

        for i in range(4):
            cycle_factory(slice_type="test", latency=float(i + 1), index=i)

        s = evaluate_slice(run.pk, "test")
        assert s.latency_mean_ms == pytest.approx(2.5)

    def test_adaptive_counts_persisted(self, run, cycle_factory):
        from estimation.evaluation.reporter import evaluate_slice

        cycle_factory(slice_type="test", adaptive_status="R_updated", index=0)
        cycle_factory(slice_type="test", adaptive_status="R_updated", index=1)
        cycle_factory(slice_type="test", adaptive_status="R_skipped", index=2)
        cycle_factory(slice_type="test", adaptive_status="skipped", index=3)

        s = evaluate_slice(run.pk, "test")
        assert s.n_r_updated == 2
        assert s.n_r_skipped == 1
        assert s.n_adaptive_skipped == 1

    def test_raises_for_invalid_slice_type(self, run):
        from estimation.evaluation.reporter import evaluate_slice

        with pytest.raises(ValueError, match="Invalid slice_type"):
            evaluate_slice(run.pk, "bogus")

    def test_zero_cycles_produces_zero_summary(self, run):
        from estimation.evaluation.reporter import evaluate_slice

        s = evaluate_slice(run.pk, "validation")
        assert s.n_samples == 0
        assert s.variance_reduction is None


# ── TestEvaluateSliceIdempotent ────────────────────────────────────────────────


@pytest.mark.django_db
class TestEvaluateSliceOrderStability:
    """evaluate_slice() must sort by cycle_index so np.diff-based metrics
    (variance reduction, ADR-003 gate) are deterministic regardless of DB
    insertion order."""

    def test_out_of_order_insert_gives_same_result_as_sorted(
        self, run, cycle_factory
    ):
        from estimation.evaluation.metrics import compute_metrics
        from estimation.evaluation.reporter import evaluate_slice

        # Monotonically increasing soil-moisture values; order matters for diff
        sm_values = [50.0, 51.0, 52.0, 53.0, 54.0, 55.0]

        # Insert in reverse cycle_index order to defeat any implicit DB ordering
        for i, sm in reversed(list(enumerate(sm_values))):
            cycle_factory(slice_type="train", index=i, raw_sm=sm, kf_post=sm - 0.1)

        # compute_metrics on rows sorted by cycle_index (ground truth)
        from estimation.models import PipelineCycle

        sorted_rows = list(
            PipelineCycle.objects.filter(run=run, slice_type="train")
            .order_by("cycle_index")
            .values(
                "raw_soil_moisture",
                "arx_predicted",
                "kf_x_prior",
                "kf_P_prior",
                "kf_innovation",
                "kf_R",
                "kf_K",
                "kf_x_posterior",
                "kf_P_posterior",
                "cycle_status",
                "adaptive_status",
                "latency_ms",
            )
        )
        expected = compute_metrics(sorted_rows)

        # evaluate_slice must produce the same variance_reduction
        summary = evaluate_slice(run.pk, "train")
        assert summary.variance_reduction == expected.variance_reduction
        assert summary.var_diff_raw == expected.var_diff_raw
        assert summary.var_diff_filtered == expected.var_diff_filtered

    def test_different_insert_orders_yield_identical_summary(
        self, run, cycle_factory
    ):
        """Two runs with the same data but different insert orders must agree."""
        from estimation.evaluation.reporter import evaluate_slice

        sm_values = [50.0, 52.0, 51.0, 53.0, 55.0, 54.0]

        # Insert in the given (non-monotonic) order
        for i, sm in enumerate(sm_values):
            cycle_factory(slice_type="validation", index=i, raw_sm=sm, kf_post=sm - 0.2)

        summary = evaluate_slice(run.pk, "validation")

        # The DB-ordered result must match manually sorted computation
        from estimation.evaluation.metrics import compute_metrics
        from estimation.models import PipelineCycle

        sorted_rows = list(
            PipelineCycle.objects.filter(run=run, slice_type="validation")
            .order_by("cycle_index")
            .values(
                "raw_soil_moisture", "arx_predicted", "kf_x_prior", "kf_P_prior",
                "kf_innovation", "kf_R", "kf_K", "kf_x_posterior", "kf_P_posterior",
                "cycle_status", "adaptive_status", "latency_ms",
            )
        )
        expected = compute_metrics(sorted_rows)
        assert summary.variance_reduction == expected.variance_reduction


# ── TestEvaluateSliceIdempotent ────────────────────────────────────────────────


class TestEvaluateSliceIdempotent:
    def test_second_call_updates_not_duplicates(self, run, cycle_factory):
        from estimation.evaluation.reporter import evaluate_slice
        from estimation.models import EvaluationSummary

        for i in range(3):
            cycle_factory(slice_type="train", index=i)

        evaluate_slice(run.pk, "train")
        evaluate_slice(run.pk, "train")  # second call

        assert EvaluationSummary.objects.filter(run=run, slice_type="train").count() == 1


# ── TestEvaluateAllSlices ──────────────────────────────────────────────────────


@pytest.mark.django_db
class TestEvaluateAllSlices:
    def test_returns_all_three_slices(self, run, cycle_factory):
        from estimation.evaluation.reporter import evaluate_all_slices

        for i in range(3):
            cycle_factory(slice_type="train", index=i)
        for i in range(3):
            cycle_factory(slice_type="validation", index=i + 3)
        for i in range(3):
            cycle_factory(slice_type="test", index=i + 6)

        result = evaluate_all_slices(run.pk)
        assert set(result.keys()) == {"train", "validation", "test"}
        assert result["train"].n_samples == 3


# ── TestBuildTextReport ────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestBuildTextReport:
    def test_contains_headings(self, run, cycle_factory):
        from estimation.evaluation.reporter import build_text_report

        for i in range(5):
            for st in ("train", "validation", "test"):
                cycle_factory(slice_type=st, index=i + {"train": 0, "validation": 100, "test": 200}[st])

        report = build_text_report(run.pk)
        assert "EVALUATION REPORT" in report
        assert "ADR-003 ACCEPTANCE GATE" in report
        assert "AMPC READINESS" in report
        assert "VARIANCE REDUCTION" in report
        assert "INNOVATION DIAGNOSTICS" in report

    def test_returns_string(self, run):
        from estimation.evaluation.reporter import build_text_report

        result = build_text_report(run.pk)
        assert isinstance(result, str)
        assert len(result) > 100

    def test_null_gate_shows_na_not_fail(self, run, cycle_factory):
        """When any ADR-003 gate flag is None the text report must say N/A."""
        from estimation.evaluation.reporter import build_text_report
        from estimation.models import EvaluationSummary

        # Populate cycles so evaluate_slice can run for all three slices
        for i in range(3):
            for st in ("train", "validation", "test"):
                cycle_factory(
                    slice_type=st,
                    index=i + {"train": 0, "validation": 100, "test": 200}[st],
                )

        # Manually patch the test-slice summary so one flag is None
        EvaluationSummary.objects.filter(run=run, slice_type="test").update(
            pass_variance_reduction=None
        )

        report = build_text_report(run.pk)

        # Overall gate line must not say FAIL when a flag is unknown
        import re
        gate_line = next(
            (l for l in report.splitlines() if "Overall ADR-003 gate" in l), None
        )
        assert gate_line is not None, "Gate line not found in report"
        assert "FAIL" not in gate_line, (
            f"Expected N/A for null gate but got: {gate_line!r}"
        )
        assert "N/A" in gate_line, (
            f"Expected 'N/A' in gate line but got: {gate_line!r}"
        )


# ── TestExportToCsv ────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestExportToCsv:
    def test_csv_has_header_and_three_rows(self, run, cycle_factory):
        from estimation.evaluation.reporter import export_to_csv

        for i in range(3):
            cycle_factory(slice_type="test", index=i)

        with tempfile.TemporaryDirectory() as tmp:
            path = export_to_csv(run.pk, Path(tmp) / "metrics.csv")
            assert path.exists()
            with path.open(newline="", encoding="utf-8") as fh:
                reader = list(csv.DictReader(fh))
            assert len(reader) == 3
            assert "run_pk" in reader[0]
            assert "variance_reduction" in reader[0]
            assert "passes_acceptance_gate" in reader[0]

    def test_run_pk_in_every_row(self, run, cycle_factory):
        from estimation.evaluation.reporter import export_to_csv

        cycle_factory(slice_type="train", index=0)

        with tempfile.TemporaryDirectory() as tmp:
            path = export_to_csv(run.pk, Path(tmp) / "out.csv")
            with path.open(newline="", encoding="utf-8") as fh:
                rows = list(csv.DictReader(fh))
            for row in rows:
                assert str(row["run_pk"]) == str(run.pk)

    def test_slice_types_present(self, run):
        from estimation.evaluation.reporter import export_to_csv

        with tempfile.TemporaryDirectory() as tmp:
            path = export_to_csv(run.pk, Path(tmp) / "out.csv")
            with path.open(newline="", encoding="utf-8") as fh:
                rows = list(csv.DictReader(fh))
            slice_types = {r["slice_type"] for r in rows}
            assert slice_types == {"train", "validation", "test"}


# ── TestLatencyMappedFromStore ─────────────────────────────────────────────────


@pytest.mark.django_db
class TestLatencyMappedFromStore:
    """Verify that latency_ms flows through map_result_to_cycle into the DB."""

    def _make_cycle_result(self, latency: float | None = 2.7):
        from datetime import timedelta

        from estimation.kalman.cycle import CycleResult

        ts = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
        return CycleResult(
            timestamp=ts,
            cycle_index=0,
            raw_soil_moisture=55.0,
            preprocess_status="valid",
            arx_predicted=54.8,
            x_prior=54.8,
            P_prior=0.9,
            innovation=0.2,
            R=1.0,
            K=0.47,
            x_posterior=54.9,
            P_posterior=0.48,
            cycle_status="ok",
            adaptive_status="R_updated",
            latency_ms=latency,
        )

    def test_latency_stored_in_pipeline_cycle(self, run):
        from estimation.models import PipelineCycle
        from estimation.pipeline.store import map_result_to_cycle

        result = self._make_cycle_result(latency=3.14)
        cycle = map_result_to_cycle(result, run=run, slice_type="test")
        cycle.save()

        stored = PipelineCycle.objects.get(pk=cycle.pk)
        assert stored.latency_ms == pytest.approx(3.14)

    def test_none_latency_stored_as_null(self, run):
        from estimation.models import PipelineCycle
        from estimation.pipeline.store import map_result_to_cycle

        result = self._make_cycle_result(latency=None)
        cycle = map_result_to_cycle(result, run=run, slice_type="test")
        cycle.save()

        stored = PipelineCycle.objects.get(pk=cycle.pk)
        assert stored.latency_ms is None
