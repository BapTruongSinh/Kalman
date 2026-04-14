"""
Adaptive Kalman-ready estimation cycle for scalar Soil_Moisture.

Algorithm — bounded innovation-driven adaptive R (Q fixed per run).
Decided in Task #001 (ADR-003).

Prediction step (time update)
------------------------------
    x_prior  = y_hat_k   if ARX prediction is available and status == "ok"
               else x_post_prev   (last posterior, carry-forward)
    P_prior  = P_post_prev + Q

Measurement update  (when z_k is available and preprocess_status != "skipped")
-------------------------------------------------------------------------------
    e_k      = z_k - x_prior
    R_k      = clip(alpha * R_{k-1} + (1 - alpha) * e_k^2, R_min, R_max)
    K_k      = P_prior / (P_prior + R_k)
    x_post   = x_prior + K_k * e_k
    P_post   = (1 - K_k) * P_prior

Measurement unavailable
-----------------------
    x_post   = x_prior   (carry prior forward)
    P_post   = P_prior   (covariance grows with Q in the next prediction step)
    R        unchanged

Design constraints
------------------
- ``step()`` **never raises** — all errors produce ``cycle_status="error"``.
- Mutable state is isolated in ``KalmanState``; config is frozen.
- The prediction adapter is an optional dependency; absence falls back cleanly.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Sequence

from ..ingestion import ProcessedRecord
from ..prediction import PredictionAdapter, PredictionInput, PredictionResult

logger = logging.getLogger(__name__)


# ── Configuration ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class KalmanConfig:
    """Hyperparameters for the Adaptive Kalman estimation cycle.

    All defaults match ADR-003 locked decisions (Task #001).

    Parameters
    ----------
    x0:
        Initial state estimate.  Set to the first observed ``Soil_Moisture``
        before starting a run.
    P0:
        Initial error covariance (> 0).
    Q:
        Process noise covariance (> 0); fixed for the duration of a run,
        tuned on the validation slice.
    R0:
        Initial measurement noise covariance (> 0); must be in [R_min, R_max].
    R_min:
        Lower bound for the adaptive R (exclusive lower bound is 0).
    R_max:
        Upper bound for the adaptive R.  Must satisfy R_min < R_max.
    alpha:
        Exponential moving-average smoothing factor for adaptive R.
        Must be in [0, 1]; higher values give R more inertia.
    """

    x0: float = 0.0
    P0: float = 1.0
    Q: float = 0.05
    R0: float = 1.0
    R_min: float = 0.05
    R_max: float = 25.0
    alpha: float = 0.95

    def __post_init__(self) -> None:
        if self.P0 <= 0.0:
            raise ValueError(f"P0 must be > 0, got {self.P0!r}")
        if self.Q <= 0.0:
            raise ValueError(f"Q must be > 0, got {self.Q!r}")
        if self.R0 <= 0.0:
            raise ValueError(f"R0 must be > 0, got {self.R0!r}")
        if not (0.0 < self.R_min < self.R_max):
            raise ValueError(
                f"Must satisfy 0 < R_min < R_max; "
                f"got R_min={self.R_min!r}, R_max={self.R_max!r}"
            )
        if not (self.R_min <= self.R0 <= self.R_max):
            raise ValueError(
                f"R0 must be in [R_min, R_max]; "
                f"got R0={self.R0!r}, R_min={self.R_min!r}, R_max={self.R_max!r}"
            )
        if not (0.0 <= self.alpha <= 1.0):
            raise ValueError(f"alpha must be in [0, 1], got {self.alpha!r}")


# ── Mutable filter state ───────────────────────────────────────────────────────


@dataclass
class KalmanState:
    """Mutable state carried between successive ``step()`` calls.

    Attributes
    ----------
    x_post:
        Current posterior estimate (filtered Soil_Moisture).
    P_post:
        Current posterior error covariance.
    R:
        Current adaptive measurement noise covariance.
    step:
        Number of time steps processed so far (0-based counter).
    """

    x_post: float
    P_post: float
    R: float
    step: int = 0

    @classmethod
    def from_config(cls, config: KalmanConfig) -> "KalmanState":
        """Initialise a fresh state from a ``KalmanConfig``."""
        return cls(x_post=config.x0, P_post=config.P0, R=config.R0)


# ── Per-cycle output ───────────────────────────────────────────────────────────


@dataclass(frozen=True)
class CycleResult:
    """Output for a single processed time step.

    Contains the Kalman subset needed to populate the ``PipelineCycle`` Django
    model (Task #002).  The storage layer (Task #007) is responsible for
    mapping these fields to the model's column names and adding run-level
    metadata (``slice_type``, ``source_type``, ``created_at``, ``kf_`` prefixes, …).

    Attributes
    ----------
    timestamp:
        Source timestamp from the dataset.
    cycle_index:
        0-based sequential index within the run.
    raw_soil_moisture:
        Raw measurement as loaded from the dataset (before preprocessing).
    preprocess_status:
        Preprocessing outcome: ``"valid"``, ``"kept_last"``,
        ``"interpolated"``, or ``"skipped"``.
    arx_predicted:
        ARX next-step prediction for Soil_Moisture; ``None`` if unavailable.
    x_prior:
        Prior (predicted) state estimate ``x^-_k`` after time update.
    P_prior:
        Prior error covariance ``P^-_k`` after time update.
    innovation:
        Measurement residual ``e_k = z_k - x_prior``; ``None`` when no update.
    R:
        Adaptive measurement noise ``R_k`` at this step.
    K:
        Kalman gain ``K_k``; ``None`` when no measurement update.
    x_posterior:
        Posterior (filtered) state estimate ``x_k``.
    P_posterior:
        Posterior error covariance ``P_k``.
    cycle_status:
        ``"ok"``                     — normal update with measurement.
        ``"skipped_no_measurement"`` — measurement absent; prior carried forward.
        ``"error"``                  — unexpected exception; state unchanged.
    adaptive_status:
        ``"R_updated"`` — adaptive R was computed this step.
        ``"R_skipped"`` — no measurement; R unchanged.
        ``"skipped"``   — step was skipped entirely (error path).
    latency_ms:
        Wall-clock time for this step in milliseconds (None on error path before timing).
    error_message:
        Human-readable description when ``cycle_status == "error"``.
    """

    # Identity
    timestamp: datetime
    cycle_index: int

    # Raw / preprocessing
    raw_soil_moisture: float | None
    preprocess_status: str

    # Prediction adapter output
    arx_predicted: float | None

    # Kalman internals
    x_prior: float
    P_prior: float
    innovation: float | None
    R: float
    K: float | None
    x_posterior: float
    P_posterior: float

    # Diagnostics
    cycle_status: str
    adaptive_status: str
    latency_ms: float | None = None
    error_message: str | None = None


# ── Estimator ─────────────────────────────────────────────────────────────────


class AdaptiveKalmanCycle:
    """Scalar Adaptive Kalman estimator for Soil_Moisture.

    One instance represents one estimation run.  Call :meth:`step` for each
    incoming ``ProcessedRecord``.  Use :meth:`replay` to process a sequence.

    Example
    -------
    ::

        config = KalmanConfig(x0=first_sm, Q=0.05)
        estimator = AdaptiveKalmanCycle(config, adapter=arx_adapter)

        for i, record in enumerate(test_records):
            result = estimator.step(record, cycle_index=i)
            print(result.x_posterior, result.R, result.cycle_status)

    Parameters
    ----------
    config:
        Frozen hyperparameter set.
    adapter:
        Optional prediction adapter.  When supplied, its ``predict()`` output
        is used as the prior mean; when absent or when prediction status is not
        ``"ok"``, the previous posterior is used.
    """

    def __init__(
        self,
        config: KalmanConfig,
        adapter: PredictionAdapter | None = None,
    ) -> None:
        self._config = config
        self._adapter = adapter
        self._state: KalmanState = KalmanState.from_config(config)
        # Causal history: records already processed, passed to adapter.predict()
        self._history: list[ProcessedRecord] = []

    # ── Public read-only access ────────────────────────────────────────────────

    @property
    def state(self) -> KalmanState:
        """Current mutable filter state (read-only reference)."""
        return self._state

    @property
    def config(self) -> KalmanConfig:
        """Frozen configuration."""
        return self._config

    @property
    def history(self) -> list[ProcessedRecord]:
        """All records processed so far (chronological order, read-only copy)."""
        return list(self._history)

    # ── Step ──────────────────────────────────────────────────────────────────

    def step(
        self,
        record: ProcessedRecord,
        *,
        cycle_index: int,
    ) -> CycleResult:
        """Process one time step.

        **Never raises** — all errors produce ``cycle_status="error"`` so the
        caller can always collect a result and continue.

        The internal history is updated and the step counter is incremented
        regardless of success or failure.

        Parameters
        ----------
        record:
            Preprocessed record for this time step.
        cycle_index:
            Caller-supplied sequential index (0-based within the run).

        Returns
        -------
        CycleResult
            Always a valid frozen result object.
        """
        t0 = time.perf_counter()
        result: CycleResult
        try:
            result = self._step_impl(record, cycle_index=cycle_index, t0=t0)
        except Exception as exc:  # noqa: BLE001
            logger.exception("KalmanCycle step %d raised unexpectedly", cycle_index)
            elapsed = (time.perf_counter() - t0) * 1000.0
            # --- safe attribute extraction so error handler itself never raises ---
            _sentinel = datetime(1970, 1, 1, tzinfo=timezone.utc)
            _raw = getattr(record, "raw", None)
            _ts: datetime = getattr(_raw, "timestamp", _sentinel)
            _raw_sm: float | None = getattr(_raw, "soil_moisture", None)
            _pre_status: str = getattr(record, "preprocess_status", "invalid")
            # State is NOT mutated in the error branch — keep last known good values.
            result = CycleResult(
                timestamp=_ts,
                cycle_index=cycle_index,
                raw_soil_moisture=_raw_sm,
                preprocess_status=_pre_status,
                arx_predicted=None,
                x_prior=self._state.x_post,
                P_prior=self._state.P_post,
                innovation=None,
                R=self._state.R,
                K=None,
                x_posterior=self._state.x_post,
                P_posterior=self._state.P_post,
                cycle_status="error",
                adaptive_status="skipped",
                latency_ms=elapsed,
                error_message=str(exc),
            )

        # Always advance history and step counter, regardless of outcome.
        # Guard against non-ProcessedRecord inputs so append itself can't raise.
        if record is not None:
            try:
                self._history.append(record)
            except Exception:  # noqa: BLE001
                pass
        self._state.step += 1
        return result

    def replay(
        self,
        records: Sequence[ProcessedRecord],
        *,
        start_index: int = 0,
    ) -> list[CycleResult]:
        """Run a full sequence and return one :class:`CycleResult` per record.

        Continues from current state; create a new :class:`AdaptiveKalmanCycle`
        instance to get a fresh state.

        Parameters
        ----------
        records:
            Sequence of preprocessed records in chronological order.
        start_index:
            Offset added to each step's ``cycle_index``.

        Returns
        -------
        list[CycleResult]
            Same length as *records*.
        """
        return [
            self.step(rec, cycle_index=start_index + i)
            for i, rec in enumerate(records)
        ]

    # ── Internal implementation ────────────────────────────────────────────────

    def _step_impl(
        self,
        record: ProcessedRecord,
        *,
        cycle_index: int,
        t0: float,
    ) -> CycleResult:
        """Core estimation logic — called inside the try/except in :meth:`step`."""
        cfg = self._config
        state = self._state

        # ── 1. Ask prediction adapter for next-step forecast ─────────────────
        # Pass only the tail of history the adapter actually needs so replay
        # stays O(n) rather than O(n²) for long sequences.
        arx_result: PredictionResult | None = None
        if self._adapter is not None:
            min_hist = getattr(self._adapter, "min_history_len", 0)
            if len(self._history) >= min_hist:
                window = (
                    self._history[-min_hist:] if min_hist > 0 else []
                )
                arx_result = self._adapter.predict(
                    PredictionInput(history=window)
                )

        arx_predicted: float | None = (
            arx_result.value
            if (arx_result is not None and arx_result.status == "ok")
            else None
        )

        # ── 2. Time update (prediction step) ─────────────────────────────────
        # Prior mean: use ARX prediction when available, else carry last posterior.
        x_prior: float = (
            arx_predicted if arx_predicted is not None else state.x_post
        )
        P_prior: float = state.P_post + cfg.Q

        # ── 3. Check measurement availability ────────────────────────────────
        z: float | None = record.soil_moisture
        preprocess_status: str = record.preprocess_status

        # A "skipped" preprocessing means measurement was actively discarded;
        # treat this the same as a missing measurement for the Kalman update.
        measurement_ok: bool = (
            z is not None and preprocess_status != "skipped"
        )

        if not measurement_ok:
            # Carry prior forward — no measurement update.
            elapsed = (time.perf_counter() - t0) * 1000.0
            # Mutate state: prior becomes new posterior.
            state.x_post = x_prior
            state.P_post = P_prior
            # R is unchanged.
            return CycleResult(
                timestamp=record.raw.timestamp,
                cycle_index=cycle_index,
                raw_soil_moisture=record.raw.soil_moisture,
                preprocess_status=preprocess_status,
                arx_predicted=arx_predicted,
                x_prior=x_prior,
                P_prior=P_prior,
                innovation=None,
                R=state.R,
                K=None,
                x_posterior=x_prior,
                P_posterior=P_prior,
                cycle_status="skipped_no_measurement",
                adaptive_status="R_skipped",
                latency_ms=elapsed,
            )

        # ── 4. Measurement update ─────────────────────────────────────────────
        assert z is not None  # confirmed above

        # Innovation (measurement residual)
        e: float = z - x_prior

        # Adaptive R: bounded exponential moving average of squared innovation.
        # R grows when innovations are large, shrinks when they are small.
        R_raw: float = cfg.alpha * state.R + (1.0 - cfg.alpha) * e * e
        R_new: float = float(max(cfg.R_min, min(cfg.R_max, R_raw)))

        # Kalman gain (scalar form for 1D state)
        K: float = P_prior / (P_prior + R_new)

        # Posterior
        x_post: float = x_prior + K * e
        P_post: float = (1.0 - K) * P_prior

        elapsed = (time.perf_counter() - t0) * 1000.0

        result = CycleResult(
            timestamp=record.raw.timestamp,
            cycle_index=cycle_index,
            raw_soil_moisture=record.raw.soil_moisture,
            preprocess_status=preprocess_status,
            arx_predicted=arx_predicted,
            x_prior=x_prior,
            P_prior=P_prior,
            innovation=e,
            R=R_new,
            K=K,
            x_posterior=x_post,
            P_posterior=P_post,
            cycle_status="ok",
            adaptive_status="R_updated",
            latency_ms=elapsed,
        )

        # Mutate state last, after CycleResult is fully constructed.
        state.x_post = x_post
        state.P_post = P_post
        state.R = R_new

        return result
