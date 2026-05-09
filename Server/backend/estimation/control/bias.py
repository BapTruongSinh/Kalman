"""Build AMPC bias state from recent Kalman/ARX residuals."""

from __future__ import annotations

from math import isfinite

from mpc.adaptive import BiasState
from mpc.config import AdaptiveConfig

from estimation.models import PipelineCycle


def build_bias_state(
    *,
    greenhouse_id: int,
    adaptive_config: AdaptiveConfig,
) -> BiasState:
    """Build a bounded moving-average bias from recent DB residuals."""

    if not adaptive_config.enabled:
        return BiasState()

    rows = list(
        PipelineCycle.objects.filter(
            greenhouse_id=greenhouse_id,
            cycle_status=PipelineCycle.CycleStatus.OK,
            preprocess_status=PipelineCycle.PreprocessStatus.VALID,
            kf_x_posterior__isnull=False,
            arx_predicted__isnull=False,
        )
        .order_by("-sample_ts", "-cycle_index")
        .only("kf_x_posterior", "arx_predicted", "sample_ts")[
            : adaptive_config.bias_window
        ]
    )
    residuals: list[float] = []
    for row in reversed(rows):
        residual = float(row.kf_x_posterior) - float(row.arx_predicted)
        if isfinite(residual):
            residuals.append(
                _clip(
                    residual,
                    -adaptive_config.max_abs_bias,
                    adaptive_config.max_abs_bias,
                )
            )
    if not residuals:
        return BiasState()
    bias = _clip(
        sum(residuals) / len(residuals),
        -adaptive_config.max_abs_bias,
        adaptive_config.max_abs_bias,
    )
    return BiasState(
        residuals=tuple(residuals),
        current_bias=bias,
        last_updated_at=rows[0].sample_ts if rows else None,
    )


def bias_snapshot(state: BiasState) -> dict[str, object]:
    return {
        "current_bias": state.current_bias,
        "bias_window_count": len(state.residuals),
        "last_updated_at": (
            state.last_updated_at.isoformat()
            if state.last_updated_at is not None
            else None
        ),
    }


def _clip(value: float, low: float, high: float) -> float:
    return min(max(value, low), high)
