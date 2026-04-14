"""
DB integration, evaluation summary persistence, and report export.

Public surface
--------------
evaluate_slice(run_pk, slice_type)  → EvaluationSummary
evaluate_all_slices(run_pk)          → dict[str, EvaluationSummary]
build_text_report(run_pk)            → str
export_to_csv(run_pk, output_path)   → Path
export_plots(run_pk, output_dir)     → list[Path]  (requires matplotlib)
"""
from __future__ import annotations

import csv
import io
import math
import textwrap
from pathlib import Path
from typing import Optional

from estimation.evaluation.metrics import (
    RMSE_RATIO_MAX,
    VARIANCE_REDUCTION_MIN,
    MAE_RATIO_MAX,
    SliceMetrics,
    compute_metrics,
)
from estimation.models import EvaluationSummary, ExperimentRun, PipelineCycle

# ── Constants ─────────────────────────────────────────────────────────────────
_ALL_SLICES = ("train", "validation", "test")
_CYCLE_VALUE_FIELDS = (
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


# ── Core evaluation ────────────────────────────────────────────────────────────


def evaluate_slice(run_pk: int, slice_type: str) -> EvaluationSummary:
    """Compute metrics for *slice_type*, persist as ``EvaluationSummary``, and return it.

    Idempotent — updates the existing row if one already exists for
    ``(run, slice_type)``.

    Parameters
    ----------
    run_pk:
        Primary key of the target ``ExperimentRun``.
    slice_type:
        One of ``"train"``, ``"validation"``, ``"test"``.

    Raises
    ------
    ValueError
        If *slice_type* is not one of the allowed values.
    ExperimentRun.DoesNotExist
        If no run with *run_pk* exists.
    """
    if slice_type not in _ALL_SLICES:
        raise ValueError(
            f"Invalid slice_type {slice_type!r}. Expected one of {sorted(_ALL_SLICES)}."
        )

    run = ExperimentRun.objects.get(pk=run_pk)
    rows = list(
        PipelineCycle.objects.filter(run=run, slice_type=slice_type)
        .order_by("cycle_index")
        .values(*_CYCLE_VALUE_FIELDS)
    )
    m = compute_metrics(rows)

    summary, _ = EvaluationSummary.objects.update_or_create(
        run=run,
        slice_type=slice_type,
        defaults=_metrics_to_defaults(m),
    )
    return summary


def evaluate_all_slices(run_pk: int) -> dict[str, EvaluationSummary]:
    """Evaluate and persist metrics for all three data slices of a run.

    Returns a dict keyed by ``"train"``, ``"validation"``, ``"test"``.
    """
    return {s: evaluate_slice(run_pk, s) for s in _ALL_SLICES}


# ── Text report ────────────────────────────────────────────────────────────────


def build_text_report(run_pk: int) -> str:
    """Build a human-readable evaluation report for all slices of *run_pk*.

    Queries ``EvaluationSummary`` rows (creating them if absent), then
    formats a structured text report suitable for inclusion in a final
    academic presentation or lab notebook.

    Returns
    -------
    str
        Multi-line formatted report.
    """
    summaries = {s: evaluate_slice(run_pk, s) for s in _ALL_SLICES}
    run = ExperimentRun.objects.get(pk=run_pk)

    lines: list[str] = []
    W = 70

    def rule(char: str = "─") -> None:
        lines.append(char * W)

    def hdr(text: str) -> None:
        rule("═")
        lines.append(f"  {text}")
        rule("═")

    def section(title: str) -> None:
        lines.append("")
        rule()
        lines.append(f"  {title}")
        rule()

    def row(label: str, *vals: object, width: int = 24) -> None:
        formatted = "".join(f"{str(v):>14}" for v in vals)
        lines.append(f"  {label:<{width}}{formatted}")

    def pct(v: Optional[float]) -> str:
        return f"{v * 100:.1f} %" if v is not None else "   N/A"

    def fmt(v: Optional[float], decimals: int = 4) -> str:
        return f"{v:.{decimals}f}" if v is not None else "N/A"

    def flag(v: Optional[bool]) -> str:
        if v is None:
            return "N/A"
        return "PASS ✓" if v else "FAIL ✗"

    slices = list(_ALL_SLICES)

    # ── Header ─────────────────────────────────────────────────────────────
    hdr(f"EVALUATION REPORT — Run #{run_pk}  ({run.created_at:%Y-%m-%d %H:%M UTC})")
    lines.append(f"  Status : {run.status}")
    lines.append(f"  Name   : {run.name or '(none)'}")
    lines.append("")

    # ── Column header ──────────────────────────────────────────────────────
    row("Metric", "Train", "Validation", "Test", width=26)
    rule()

    section("SAMPLE COUNTS & CYCLE SUCCESS")
    row("Total samples", *[s.n_samples for s in summaries.values()], width=26)
    row("Valid (ok) cycles", *[s.n_valid for s in summaries.values()], width=26)
    row("Skipped cycles", *[s.n_skipped for s in summaries.values()], width=26)
    row("Error cycles", *[s.n_error for s in summaries.values()], width=26)
    row(
        "Cycle success rate",
        *[pct(s.cycle_success_rate) for s in summaries.values()],
        width=26,
    )
    row(
        "Sample loss rate",
        *[pct(s.sample_loss_rate) for s in summaries.values()],
        width=26,
    )

    section("LATENCY")
    row(
        "Mean latency (ms)",
        *[fmt(s.latency_mean_ms, 2) for s in summaries.values()],
        width=26,
    )
    row(
        "P95  latency (ms)",
        *[fmt(s.latency_p95_ms, 2) for s in summaries.values()],
        width=26,
    )

    section("ARX BASELINE ACCURACY  (vs raw reference)")
    row("RMSE — ARX", *[fmt(s.rmse_arx) for s in summaries.values()], width=26)
    row("MAE  — ARX", *[fmt(s.mae_arx) for s in summaries.values()], width=26)

    section("KALMAN FILTER ACCURACY  (vs raw reference)")
    row(
        "RMSE — Kalman filtered",
        *[fmt(s.rmse_filtered) for s in summaries.values()],
        width=26,
    )
    row(
        "MAE  — Kalman filtered",
        *[fmt(s.mae_filtered) for s in summaries.values()],
        width=26,
    )
    row(
        "RMSE ratio (KF / ARX)",
        *[fmt(s.rmse_ratio) for s in summaries.values()],
        width=26,
    )
    row(
        "MAE  ratio (KF / ARX)",
        *[fmt(s.mae_ratio) for s in summaries.values()],
        width=26,
    )

    section("VARIANCE REDUCTION  (ADR-003)")
    row(
        "var(diff(raw))",
        *[fmt(s.var_diff_raw) for s in summaries.values()],
        width=26,
    )
    row(
        "var(diff(filtered))",
        *[fmt(s.var_diff_filtered) for s in summaries.values()],
        width=26,
    )
    row(
        "Variance reduction",
        *[pct(s.variance_reduction) for s in summaries.values()],
        width=26,
    )

    section("INNOVATION DIAGNOSTICS")
    row(
        "Innovation mean",
        *[fmt(s.innovation_mean) for s in summaries.values()],
        width=26,
    )
    row(
        "Innovation std",
        *[fmt(s.innovation_std) for s in summaries.values()],
        width=26,
    )
    row(
        "Innovation max |e|",
        *[fmt(s.innovation_max_abs) for s in summaries.values()],
        width=26,
    )

    section("ADAPTIVE R DIAGNOSTICS")
    row("R mean", *[fmt(s.R_mean) for s in summaries.values()], width=26)
    row("R min observed", *[fmt(s.R_min_observed) for s in summaries.values()], width=26)
    row("R max observed", *[fmt(s.R_max_observed) for s in summaries.values()], width=26)
    row("R_updated cycles", *[s.n_r_updated for s in summaries.values()], width=26)
    row("R_skipped cycles", *[s.n_r_skipped for s in summaries.values()], width=26)
    row("Adaptive error cycles", *[s.n_adaptive_skipped for s in summaries.values()], width=26)

    section("POSTERIOR COVARIANCE")
    row("P mean", *[fmt(s.P_mean) for s in summaries.values()], width=26)
    row("P max", *[fmt(s.P_max) for s in summaries.values()], width=26)

    # ── ADR-003 gate (test slice only) ─────────────────────────────────────
    test = summaries["test"]
    section("ADR-003 ACCEPTANCE GATE  (Test slice)")
    lines.append(
        f"  Variance reduction >= {VARIANCE_REDUCTION_MIN * 100:.0f} %"
        f"    {pct(test.variance_reduction):>10}    {flag(test.pass_variance_reduction)}"
    )
    lines.append(
        f"  RMSE ratio <= {RMSE_RATIO_MAX:.2f}"
        f"              {fmt(test.rmse_ratio):>10}    {flag(test.pass_rmse_guardrail)}"
    )
    lines.append(
        f"  MAE  ratio <= {MAE_RATIO_MAX:.2f}"
        f"              {fmt(test.mae_ratio):>10}    {flag(test.pass_mae_guardrail)}"
    )
    rule()
    gate_label = "PASS" if test.passes_acceptance_gate else "FAIL"
    lines.append(f"  Overall ADR-003 gate:  {gate_label}")

    # ── AMPC readiness placeholder ─────────────────────────────────────────
    section("AMPC READINESS (v1 — placeholder)")
    lines.append(
        textwrap.fill(
            "State estimate (Soil_Moisture) and adaptive R/P are logged per cycle, "
            "providing the state-noise contracts needed for an AMPC cost function.",
            width=W - 4,
            initial_indent="  ",
            subsequent_indent="  ",
        )
    )
    lines.append(
        textwrap.fill(
            "Dr (root-zone depletion) derivation is DEFERRED to v2 "
            "(requires field capacity, wilting point, and root-zone depth parameters).",
            width=W - 4,
            initial_indent="  ",
            subsequent_indent="  ",
        )
    )
    lines.append(
        "  Full closed-loop controller simulation: OUT OF SCOPE for v1."
    )
    rule("═")

    return "\n".join(lines)


# ── CSV export ─────────────────────────────────────────────────────────────────


def export_to_csv(run_pk: int, output_path: "Path | str") -> Path:
    """Export evaluation metrics for all slices of *run_pk* to a CSV file.

    Each slice becomes one row.  The file is created (or overwritten) at
    *output_path*.

    Returns
    -------
    Path
        Path of the written file.
    """
    summaries = {s: evaluate_slice(run_pk, s) for s in _ALL_SLICES}
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "run_pk",
        "slice_type",
        "n_samples",
        "n_valid",
        "n_skipped",
        "n_error",
        "cycle_success_rate",
        "sample_loss_rate",
        "n_r_updated",
        "n_r_skipped",
        "n_adaptive_skipped",
        "latency_mean_ms",
        "latency_p95_ms",
        "rmse_arx",
        "mae_arx",
        "rmse_filtered",
        "mae_filtered",
        "var_diff_raw",
        "var_diff_filtered",
        "variance_reduction",
        "rmse_ratio",
        "mae_ratio",
        "innovation_mean",
        "innovation_std",
        "innovation_max_abs",
        "R_mean",
        "R_min_observed",
        "R_max_observed",
        "P_mean",
        "P_max",
        "pass_variance_reduction",
        "pass_rmse_guardrail",
        "pass_mae_guardrail",
        "passes_acceptance_gate",
    ]

    with output.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for slice_type, s in summaries.items():
            writer.writerow(
                {
                    "run_pk": run_pk,
                    "slice_type": slice_type,
                    "n_samples": s.n_samples,
                    "n_valid": s.n_valid,
                    "n_skipped": s.n_skipped,
                    "n_error": s.n_error,
                    "cycle_success_rate": s.cycle_success_rate,
                    "sample_loss_rate": s.sample_loss_rate,
                    "n_r_updated": s.n_r_updated,
                    "n_r_skipped": s.n_r_skipped,
                    "n_adaptive_skipped": s.n_adaptive_skipped,
                    "latency_mean_ms": s.latency_mean_ms,
                    "latency_p95_ms": s.latency_p95_ms,
                    "rmse_arx": s.rmse_arx,
                    "mae_arx": s.mae_arx,
                    "rmse_filtered": s.rmse_filtered,
                    "mae_filtered": s.mae_filtered,
                    "var_diff_raw": s.var_diff_raw,
                    "var_diff_filtered": s.var_diff_filtered,
                    "variance_reduction": s.variance_reduction,
                    "rmse_ratio": s.rmse_ratio,
                    "mae_ratio": s.mae_ratio,
                    "innovation_mean": s.innovation_mean,
                    "innovation_std": s.innovation_std,
                    "innovation_max_abs": s.innovation_max_abs,
                    "R_mean": s.R_mean,
                    "R_min_observed": s.R_min_observed,
                    "R_max_observed": s.R_max_observed,
                    "P_mean": s.P_mean,
                    "P_max": s.P_max,
                    "pass_variance_reduction": s.pass_variance_reduction,
                    "pass_rmse_guardrail": s.pass_rmse_guardrail,
                    "pass_mae_guardrail": s.pass_mae_guardrail,
                    "passes_acceptance_gate": s.passes_acceptance_gate,
                }
            )

    return output


# ── Plot export ────────────────────────────────────────────────────────────────


def export_plots(run_pk: int, output_dir: "Path | str") -> list[Path]:
    """Generate diagnostic plots for all slices of *run_pk*.

    Produces up to four plots per slice:
    1. ``time_series_{slice}.png``  — raw / ARX predicted / Kalman filtered
    2. ``innovation_{slice}.png``   — innovation sequence
    3. ``adaptive_R_{slice}.png``   — adaptive measurement noise R
    4. ``residuals_{slice}.png``    — histogram of (raw − filtered) residuals
       (only written when at least one paired raw/filtered value is present)

    Requires ``matplotlib`` to be importable with the current numpy ABI.
    Returns an empty list (with a warning) if matplotlib is unavailable.

    Returns
    -------
    list[Path]
        Paths of the generated PNG files.
    """
    # Lazy import — only this function touches matplotlib so the ABI
    # traceback (if any) never appears when calling evaluate_slice or
    # build_text_report.
    try:
        import matplotlib  # noqa: PLC0415

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt  # noqa: PLC0415
        import matplotlib.dates as mdates  # noqa: PLC0415
    except Exception:  # ImportError or numpy ABI mismatch
        import warnings

        warnings.warn(
            "matplotlib is not available (possible numpy ABI mismatch). "
            "Skipping plot export for run #%d." % run_pk,
            RuntimeWarning,
            stacklevel=2,
        )
        return []

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    generated: list[Path] = []

    for slice_type in _ALL_SLICES:
        qs = (
            PipelineCycle.objects.filter(run_id=run_pk, slice_type=slice_type)
            .order_by("cycle_index")
            .values(
                "sample_ts",
                "raw_soil_moisture",
                "arx_predicted",
                "kf_x_posterior",
                "kf_innovation",
                "kf_R",
            )
        )
        rows = list(qs)
        if not rows:
            continue

        ts = [r["sample_ts"] for r in rows]
        raw = [r.get("raw_soil_moisture") for r in rows]
        arx = [r.get("arx_predicted") for r in rows]
        kf = [r.get("kf_x_posterior") for r in rows]
        inn = [r.get("kf_innovation") for r in rows]
        R_val = [r.get("kf_R") for r in rows]

        # 1. Time-series ───────────────────────────────────────────────────────
        fig, ax = plt.subplots(figsize=(14, 4))
        ax.plot(ts, raw, lw=0.6, color="steelblue", alpha=0.7, label="Raw")
        ax.plot(ts, arx, lw=0.8, color="orange", alpha=0.8, label="ARX predicted")
        ax.plot(ts, kf, lw=1.0, color="crimson", alpha=0.9, label="Kalman filtered")
        ax.set_title(f"Soil Moisture — {slice_type.capitalize()} slice  (Run #{run_pk})")
        ax.set_xlabel("Time")
        ax.set_ylabel("Soil Moisture (%)")
        ax.legend(loc="upper right", fontsize=8)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M"))
        fig.autofmt_xdate()
        path = out / f"time_series_{slice_type}.png"
        fig.savefig(path, dpi=120, bbox_inches="tight")
        plt.close(fig)
        generated.append(path)

        # 2. Innovation ────────────────────────────────────────────────────────
        fig, ax = plt.subplots(figsize=(14, 3))
        ax.plot(ts, inn, lw=0.7, color="seagreen", label="Innovation e_k")
        ax.axhline(0, color="black", lw=0.5, ls="--")
        ax.set_title(f"Innovation — {slice_type.capitalize()} slice  (Run #{run_pk})")
        ax.set_xlabel("Time")
        ax.set_ylabel("Innovation")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M"))
        fig.autofmt_xdate()
        path = out / f"innovation_{slice_type}.png"
        fig.savefig(path, dpi=120, bbox_inches="tight")
        plt.close(fig)
        generated.append(path)

        # 3. Adaptive R ────────────────────────────────────────────────────────
        fig, ax = plt.subplots(figsize=(14, 3))
        ax.plot(ts, R_val, lw=0.8, color="darkorchid", label="Adaptive R_k")
        ax.set_title(f"Adaptive R — {slice_type.capitalize()} slice  (Run #{run_pk})")
        ax.set_xlabel("Time")
        ax.set_ylabel("Measurement Noise R")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M"))
        fig.autofmt_xdate()
        path = out / f"adaptive_R_{slice_type}.png"
        fig.savefig(path, dpi=120, bbox_inches="tight")
        plt.close(fig)
        generated.append(path)

        # 4. Residuals histogram ───────────────────────────────────────────────
        residuals = [
            r - k
            for r, k in zip(raw, kf)
            if r is not None and k is not None
            and math.isfinite(r) and math.isfinite(k)
        ]
        if residuals:
            fig, ax = plt.subplots(figsize=(6, 4))
            ax.hist(residuals, bins=50, color="tomato", edgecolor="white", alpha=0.8)
            ax.axvline(0, color="black", lw=1, ls="--")
            ax.set_title(
                f"Residuals (raw − filtered) — {slice_type.capitalize()}  (Run #{run_pk})"
            )
            ax.set_xlabel("Residual")
            ax.set_ylabel("Count")
            path = out / f"residuals_{slice_type}.png"
            fig.savefig(path, dpi=120, bbox_inches="tight")
            plt.close(fig)
            generated.append(path)

    return generated


# ── Internal helpers ───────────────────────────────────────────────────────────


def _metrics_to_defaults(m: SliceMetrics) -> dict:
    """Map a ``SliceMetrics`` instance to an ``EvaluationSummary`` defaults dict."""
    return {
        "n_samples": m.n_samples,
        "n_valid": m.n_valid,
        "n_skipped": m.n_skipped,
        "n_error": m.n_error,
        "n_r_updated": m.n_r_updated,
        "n_r_skipped": m.n_r_skipped,
        "n_adaptive_skipped": m.n_adaptive_skipped,
        "latency_mean_ms": m.latency_mean_ms,
        "latency_p95_ms": m.latency_p95_ms,
        "rmse_arx": m.rmse_arx,
        "mae_arx": m.mae_arx,
        "rmse_filtered": m.rmse_filtered,
        "mae_filtered": m.mae_filtered,
        "var_diff_raw": m.var_diff_raw,
        "var_diff_filtered": m.var_diff_filtered,
        "variance_reduction": m.variance_reduction,
        "rmse_ratio": m.rmse_ratio,
        "mae_ratio": m.mae_ratio,
        "innovation_mean": m.innovation_mean,
        "innovation_std": m.innovation_std,
        "innovation_max_abs": m.innovation_max_abs,
        "R_mean": m.R_mean,
        "R_min_observed": m.R_min_observed,
        "R_max_observed": m.R_max_observed,
        "P_mean": m.P_mean,
        "P_max": m.P_max,
        "pass_variance_reduction": m.pass_variance_reduction,
        "pass_rmse_guardrail": m.pass_rmse_guardrail,
        "pass_mae_guardrail": m.pass_mae_guardrail,
    }
