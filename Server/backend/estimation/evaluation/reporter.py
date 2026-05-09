"""
Tích hợp DB, lưu summary đánh giá và export báo cáo.

Các hàm public
--------------
evaluate_online(run_pk)              → EvaluationSummary
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

from kalman.evaluation import (
    RMSE_RATIO_MAX,
    VARIANCE_REDUCTION_MIN,
    MAE_RATIO_MAX,
    SliceMetrics,
    compute_metrics,
)
from estimation.models import EvaluationSummary, ExperimentRun, PipelineCycle

# ── Hằng số ──────────────────────────────────────────────────────────────────
ONLINE_SLICE = "online"
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


# ── Đánh giá chính ───────────────────────────────────────────────────────────


def evaluate_slice(run_pk: int, slice_type: str = ONLINE_SLICE) -> EvaluationSummary:
    """Tính metric online, lưu vào ``EvaluationSummary`` rồi trả về.

    Hàm idempotent: nếu đã có dòng cho ``(run, slice_type)`` thì update dòng đó.

    Parameters
    ----------
    run_pk:
        Primary key của ``ExperimentRun`` cần đánh giá.
    slice_type:
        Chỉ hỗ trợ ``"online"`` sau cleanup runtime live-only.

    Raises
    ------
    ValueError
        Nếu *slice_type* không phải ``"online"``.
    ExperimentRun.DoesNotExist
        Nếu không có run với *run_pk*.
    """
    if slice_type != ONLINE_SLICE:
        raise ValueError(
            f"Invalid slice_type {slice_type!r}. Expected 'online'."
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


def evaluate_online(run_pk: int) -> EvaluationSummary:
    """Đánh giá và lưu metric cho toàn bộ stream online của một run."""
    return evaluate_slice(run_pk, ONLINE_SLICE)


# ── Báo cáo text ─────────────────────────────────────────────────────────────


def build_text_report(run_pk: int) -> str:
    """Tạo báo cáo đánh giá dễ đọc cho mọi slice của *run_pk*.

    Query các dòng ``EvaluationSummary`` (tạo nếu chưa có), sau đó format thành
    báo cáo text có cấu trúc để đưa vào slide học thuật hoặc lab notebook.

    Returns
    -------
    str
        Báo cáo nhiều dòng đã format.
    """
    summary = evaluate_online(run_pk)
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

    # ── Phần đầu báo cáo ──────────────────────────────────────────────────
    hdr(f"EVALUATION REPORT — Run #{run_pk}  ({run.created_at:%Y-%m-%d %H:%M UTC})")
    lines.append(f"  Status : {run.status}")
    lines.append(f"  Name   : {run.name or '(none)'}")
    lines.append("")

    # ── Header cột ────────────────────────────────────────────────────────
    row("Metric", "Online", width=26)
    rule()

    section("SAMPLE COUNTS & CYCLE SUCCESS")
    row("Total samples", summary.n_samples, width=26)
    row("Valid (ok) cycles", summary.n_valid, width=26)
    row("Skipped cycles", summary.n_skipped, width=26)
    row("Error cycles", summary.n_error, width=26)
    row(
        "Cycle success rate",
        pct(summary.cycle_success_rate),
        width=26,
    )
    row(
        "Sample loss rate",
        pct(summary.sample_loss_rate),
        width=26,
    )

    section("LATENCY")
    row(
        "Mean latency (ms)",
        fmt(summary.latency_mean_ms, 2),
        width=26,
    )
    row(
        "P95  latency (ms)",
        fmt(summary.latency_p95_ms, 2),
        width=26,
    )

    section("ARX BASELINE ACCURACY  (vs raw reference)")
    row("RMSE — ARX", fmt(summary.rmse_arx), width=26)
    row("MAE  — ARX", fmt(summary.mae_arx), width=26)

    section("KALMAN FILTER ACCURACY  (vs raw reference)")
    row(
        "RMSE — Kalman filtered",
        fmt(summary.rmse_filtered),
        width=26,
    )
    row(
        "MAE  — Kalman filtered",
        fmt(summary.mae_filtered),
        width=26,
    )
    row(
        "RMSE ratio (KF / ARX)",
        fmt(summary.rmse_ratio),
        width=26,
    )
    row(
        "MAE  ratio (KF / ARX)",
        fmt(summary.mae_ratio),
        width=26,
    )

    section("VARIANCE REDUCTION")
    row(
        "var(diff(raw))",
        fmt(summary.var_diff_raw),
        width=26,
    )
    row(
        "var(diff(filtered))",
        fmt(summary.var_diff_filtered),
        width=26,
    )
    row(
        "Variance reduction",
        pct(summary.variance_reduction),
        width=26,
    )

    section("INNOVATION DIAGNOSTICS")
    row(
        "Innovation mean",
        fmt(summary.innovation_mean),
        width=26,
    )
    row(
        "Innovation std",
        fmt(summary.innovation_std),
        width=26,
    )
    row(
        "Innovation max |e|",
        fmt(summary.innovation_max_abs),
        width=26,
    )

    section("ADAPTIVE R DIAGNOSTICS")
    row("R mean", fmt(summary.R_mean), width=26)
    row("R min observed", fmt(summary.R_min_observed), width=26)
    row("R max observed", fmt(summary.R_max_observed), width=26)
    row("R_updated cycles", summary.n_r_updated, width=26)
    row("R_skipped cycles", summary.n_r_skipped, width=26)
    row("Adaptive error cycles", summary.n_adaptive_skipped, width=26)

    section("POSTERIOR COVARIANCE")
    row("P mean", fmt(summary.P_mean), width=26)
    row("P max", fmt(summary.P_max), width=26)

    # ── Online gate ───────────────────────────────────────────────────────
    section("ONLINE ACCEPTANCE GATE")
    lines.append(
        f"  Variance reduction >= {VARIANCE_REDUCTION_MIN * 100:.0f} %"
        f"    {pct(summary.variance_reduction):>10}    {flag(summary.pass_variance_reduction)}"
    )
    lines.append(
        f"  RMSE ratio <= {RMSE_RATIO_MAX:.2f}"
        f"              {fmt(summary.rmse_ratio):>10}    {flag(summary.pass_rmse_guardrail)}"
    )
    lines.append(
        f"  MAE  ratio <= {MAE_RATIO_MAX:.2f}"
        f"              {fmt(summary.mae_ratio):>10}    {flag(summary.pass_mae_guardrail)}"
    )
    rule()
    _gate = summary.passes_acceptance_gate
    gate_label = "PASS ✓" if _gate is True else ("FAIL ✗" if _gate is False else "N/A (flags incomplete)")
    lines.append(f"  Overall online gate:  {gate_label}")

    # ── Placeholder mức sẵn sàng cho AMPC ─────────────────────────────────
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


# ── Export CSV ───────────────────────────────────────────────────────────────


def export_to_csv(run_pk: int, output_path: "Path | str") -> Path:
    """Export metric đánh giá online thuộc *run_pk* ra file CSV.

    Returns
    -------
    Path
        Đường dẫn file đã ghi.
    """
    summary = evaluate_online(run_pk)
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
        writer.writerow(
            {
                "run_pk": run_pk,
                "slice_type": ONLINE_SLICE,
                "n_samples": summary.n_samples,
                "n_valid": summary.n_valid,
                "n_skipped": summary.n_skipped,
                "n_error": summary.n_error,
                "cycle_success_rate": summary.cycle_success_rate,
                "sample_loss_rate": summary.sample_loss_rate,
                "n_r_updated": summary.n_r_updated,
                "n_r_skipped": summary.n_r_skipped,
                "n_adaptive_skipped": summary.n_adaptive_skipped,
                "latency_mean_ms": summary.latency_mean_ms,
                "latency_p95_ms": summary.latency_p95_ms,
                "rmse_arx": summary.rmse_arx,
                "mae_arx": summary.mae_arx,
                "rmse_filtered": summary.rmse_filtered,
                "mae_filtered": summary.mae_filtered,
                "var_diff_raw": summary.var_diff_raw,
                "var_diff_filtered": summary.var_diff_filtered,
                "variance_reduction": summary.variance_reduction,
                "rmse_ratio": summary.rmse_ratio,
                "mae_ratio": summary.mae_ratio,
                "innovation_mean": summary.innovation_mean,
                "innovation_std": summary.innovation_std,
                "innovation_max_abs": summary.innovation_max_abs,
                "R_mean": summary.R_mean,
                "R_min_observed": summary.R_min_observed,
                "R_max_observed": summary.R_max_observed,
                "P_mean": summary.P_mean,
                "P_max": summary.P_max,
                "pass_variance_reduction": summary.pass_variance_reduction,
                "pass_rmse_guardrail": summary.pass_rmse_guardrail,
                "pass_mae_guardrail": summary.pass_mae_guardrail,
                "passes_acceptance_gate": summary.passes_acceptance_gate,
            }
        )

    return output


# ── Export biểu đồ ───────────────────────────────────────────────────────────


def export_plots(run_pk: int, output_dir: "Path | str") -> list[Path]:
    """Sinh biểu đồ chẩn đoán cho mọi slice của *run_pk*.

    Sinh tối đa bốn biểu đồ cho mỗi slice:
    1. ``time_series_{slice}.png``: raw / ARX predicted / Kalman filtered
    2. ``innovation_{slice}.png``: chuỗi innovation
    3. ``adaptive_R_{slice}.png``: nhiễu đo lường thích nghi R
    4. ``residuals_{slice}.png``: histogram của phần dư (raw − filtered), chỉ
       ghi khi có ít nhất một cặp raw/filtered hợp lệ.

    Cần import được ``matplotlib`` với ABI numpy hiện tại. Nếu không có
    matplotlib thì trả list rỗng và warning.

    Returns
    -------
    list[Path]
        Đường dẫn các file PNG đã sinh.
    """
    # Import lazy: chỉ hàm này đụng tới matplotlib, nên traceback ABI (nếu có)
    # không xuất hiện khi gọi evaluate_slice hoặc build_text_report.
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

    for slice_type in (ONLINE_SLICE,):
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

        # 1. Chuỗi thời gian ──────────────────────────────────────────────────
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

        # 2. Innovation ───────────────────────────────────────────────────────
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

        # 3. R thích nghi ─────────────────────────────────────────────────────
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

        # 4. Histogram phần dư ────────────────────────────────────────────────
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


# ── Helper nội bộ ────────────────────────────────────────────────────────────


def _metrics_to_defaults(m: SliceMetrics) -> dict:
    """Map một ``SliceMetrics`` sang dict defaults của ``EvaluationSummary``."""
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
