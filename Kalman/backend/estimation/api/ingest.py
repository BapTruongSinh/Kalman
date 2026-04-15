"""
Live sensor ingestion endpoint (Task #010).

Endpoint
--------
``POST /api/ingest/samples/``

Accepts one sensor reading, runs it through the same
validation/preprocessing pipeline as offline CSV replay, applies one Kalman
step, persists the ``PipelineCycle`` row, and returns the filtered estimate.

Design notes
------------
Authentication
    DRF ``TokenAuthentication``.  Only this endpoint requires a token —
    existing read-only dashboard views remain unauthenticated so the
    dashboard is unaffected.

    Provision a token::

        python manage.py drf_create_token <username>

    Then include the header ``Authorization: Token <key>`` in every POST.

Reconnect safety
    Kalman state (x_post, P_post, R) is loaded from the *last persisted*
    ``PipelineCycle`` on each request.  The device may disconnect and
    reconnect freely — the filter resumes from where it left off.

Gap handling
    Timestamp gaps (device down-time, missed samples) are tolerated.
    Our Kalman model is not time-varying (Q is fixed), so a gap is handled
    the same as a normal step with no special treatment needed.

ARX prediction
    Intentionally absent for the v1 live path.  Training ARX requires a
    batch of offline data; the adapter is ``None`` so the Kalman prior
    falls back to the previous posterior.  A trained ARX artifact can be
    wired in a future task once we have a dataset from the live device.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from django.db import IntegrityError, transaction
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from ..ingestion.loader import RawRecord
from ..ingestion.preprocessor import preprocess_single
from ..ingestion.validator import DEFAULT_CONFIG as DEFAULT_VALIDATION_CONFIG
from ..ingestion.validator import validate_live_record
from ..kalman import AdaptiveKalmanCycle
from ..kalman.cycle import KalmanConfig, KalmanState
from ..models import ExperimentConfig, ExperimentRun, PipelineCycle
from ..pipeline.store import map_result_to_cycle
from .live_serializers import LiveSampleSerializer

logger = logging.getLogger(__name__)

_SENSOR_FIELDS = (
    "soil_moisture",
    "temperature",
    "humidity",
    "light",
    "drip",
    "mist",
    "fan",
)


# ── Helpers ────────────────────────────────────────────────────────────────────


def _kalman_config_from_db(exp_config: ExperimentConfig) -> KalmanConfig:
    """Build a :class:`~..kalman.cycle.KalmanConfig` from a stored snapshot."""
    return KalmanConfig(
        x0=exp_config.x0,
        P0=exp_config.P0,
        Q=exp_config.Q,
        R0=exp_config.R0,
        R_min=exp_config.R_min,
        R_max=exp_config.R_max,
        alpha=exp_config.alpha,
    )


def _restore_state(
    last_cycle: PipelineCycle | None,
    config: KalmanConfig,
) -> tuple[KalmanState, int]:
    """Reconstruct filter state and the next ``cycle_index`` from the DB.

    Parameters
    ----------
    last_cycle:
        Most recent :class:`~..models.PipelineCycle` for the run, or
        ``None`` if no cycles have been stored yet.
    config:
        Active :class:`~..kalman.cycle.KalmanConfig` for the run.

    Returns
    -------
    (state, cycle_index)
        *state* to inject into the estimator before calling ``step()``.
        *cycle_index* is the 0-based index to assign this new step.

    Notes
    -----
    When the last cycle has ``None`` for any Kalman field (e.g. after an
    error cycle), state is reset from *config*.  This ensures a clean
    reconnect even after a previous step failure.
    """
    if last_cycle is None:
        return KalmanState.from_config(config), 0

    next_index = last_cycle.cycle_index + 1
    x_post = last_cycle.kf_x_posterior
    p_post = last_cycle.kf_P_posterior
    r_val = last_cycle.kf_R

    if (
        x_post is None
        or p_post is None
        or r_val is None
        or p_post <= 0.0
        or r_val <= 0.0
    ):
        logger.warning(
            "Live run %d: last cycle %d has incomplete Kalman fields "
            "(x=%s P=%s R=%s); resetting state from config.",
            last_cycle.run_id,
            last_cycle.cycle_index,
            x_post,
            p_post,
            r_val,
        )
        return KalmanState.from_config(config), next_index

    return (
        KalmanState(x_post=x_post, P_post=p_post, R=r_val, step=next_index),
        next_index,
    )


def _normalize_sample_ts(ts: datetime) -> datetime:
    """Return *ts* as timezone-aware UTC (naïve values are treated as UTC)."""
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts


def _live_ingest_response_body(
    *,
    cycle_index: int,
    preprocess_status: str,
    cycle_status: str,
    adaptive_status: str,
    kf_x_posterior: float | None,
    kf_innovation: float | None,
    idempotent: bool = False,
) -> dict:
    """JSON body for successful live ingest (201 or idempotent 200)."""
    body: dict = {
        "cycle_index": cycle_index,
        "preprocess_status": preprocess_status,
        "cycle_status": cycle_status,
        "adaptive_status": adaptive_status,
        "kf_x_posterior": kf_x_posterior,
        "kf_innovation": kf_innovation,
    }
    if idempotent:
        body["idempotent"] = True
    return body


def _response_from_pipeline_cycle(
    cycle: PipelineCycle, *, idempotent: bool = False
) -> dict:
    """Build the public JSON body from a persisted :class:`~..models.PipelineCycle`."""
    return _live_ingest_response_body(
        cycle_index=cycle.cycle_index,
        preprocess_status=cycle.preprocess_status,
        cycle_status=cycle.cycle_status,
        adaptive_status=cycle.adaptive_status,
        kf_x_posterior=cycle.kf_x_posterior,
        kf_innovation=cycle.kf_innovation,
        idempotent=idempotent,
    )


def _build_raw_record(data: dict, row_index: int) -> RawRecord:
    """Convert validated serializer data to a :class:`~..ingestion.loader.RawRecord`.

    The timestamp is made UTC-aware when it arrives as naïve.
    """
    ts = _normalize_sample_ts(data["timestamp"])
    return RawRecord(
        timestamp=ts,
        soil_moisture=data.get("soil_moisture"),
        temperature=data.get("temperature"),
        humidity=data.get("humidity"),
        light=data.get("light"),
        drip=data.get("drip"),
        mist=data.get("mist"),
        fan=data.get("fan"),
        row_index=row_index,
    )


# ── View ───────────────────────────────────────────────────────────────────────


class LiveIngestView(APIView):
    """Accept one live sensor sample and run a single Kalman step.

    **Authentication**: ``Authorization: Token <key>`` header required.

    **Request body** (JSON):

    .. code-block:: json

        {
            "run_id": 42,
            "timestamp": "2026-04-14T12:00:00Z",
            "soil_moisture": 45.3,
            "temperature": 22.1,
            "humidity": 65.0,
            "light": 120.0,
            "drip": 0.0,
            "mist": 0.0,
            "fan": 1.0
        }

    All sensor channels except ``timestamp`` and ``run_id`` are optional and
    accept ``null``.

    **Responses**:

    * ``201 Created`` — sample accepted; body contains filtered estimate.
    * ``200 OK`` — same ``run_id`` + ``timestamp`` was already ingested; body is
      the existing cycle (``"idempotent": true``). Safe for transport retries.
    * ``400 Bad Request`` — invalid payload (missing required fields, wrong types).
    * ``401 Unauthorized`` — missing or invalid token.
    * ``403 Forbidden`` — authenticated user is not the run ``owner``, or the
      live run has no ``owner`` assigned (ingestion disabled until one is set).
    * ``404 Not Found`` — ``run_id`` does not exist or is not a live run.
    * ``409 Conflict`` — run exists but is not in ``"running"`` status.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:  # noqa: PLR0911
        # ── Deserialize + validate payload ────────────────────────────────────
        serializer = LiveSampleSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        run_id: int = data["run_id"]

        # ── Fast pre-check: reject obviously wrong run_id before acquiring lock ─
        # This is an optimistic guard only — the authoritative checks (type and
        # status) happen inside the atomic block where the row is locked.
        if not ExperimentRun.objects.filter(
            pk=run_id, run_type=ExperimentRun.RunType.LIVE
        ).exists():
            return Response(
                {"error": f"Live ExperimentRun id={run_id} not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # ── Atomic: lock run row, re-check state, reconstruct, step, persist ───
        # ALL state-sensitive guards (run_type, status) are evaluated *after*
        # acquiring the row lock so that a concurrent status transition
        # (running → completed) cannot slip through between the pre-check and
        # the write.  This eliminates the TOCTOU race reported in the audit.
        #
        # The unique constraint on (run, cycle_index) is also protected by the
        # same lock — only one request per run can compute and save a new
        # cycle_index at a time.
        with transaction.atomic():
            # Lock + eager-load config in a single query.
            try:
                run = ExperimentRun.objects.select_for_update().select_related(
                    "config"
                ).get(pk=run_id, run_type=ExperimentRun.RunType.LIVE)
            except ExperimentRun.DoesNotExist:
                return Response(
                    {"error": f"Live ExperimentRun id={run_id} not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # Object-level authorization: only the assigned owner may ingest.
            if run.owner_id is None:
                return Response(
                    {
                        "error": (
                            "This live run has no owner assigned; ingestion is "
                            "disabled until owner is set on the ExperimentRun."
                        )
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
            if run.owner_id != request.user.pk:
                return Response(
                    {
                        "error": (
                            "You do not have permission to ingest samples for "
                            "this run."
                        )
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

            # Authoritative status guard — evaluated with the row lock held.
            if run.status != ExperimentRun.Status.RUNNING:
                return Response(
                    {
                        "error": (
                            f"Run {run_id} is '{run.status}', not 'running'. "
                            "Transition the run to 'running' before sending samples."
                        )
                    },
                    status=status.HTTP_409_CONFLICT,
                )

            # Load Kalman config from the already-fetched relation (no extra query).
            try:
                kalman_config = _kalman_config_from_db(run.config)
            except ExperimentConfig.DoesNotExist:
                logger.warning(
                    "Live run %d has no ExperimentConfig; using ADR-003 defaults.",
                    run_id,
                )
                kalman_config = KalmanConfig()

            sample_ts = _normalize_sample_ts(data["timestamp"])
            existing_live = (
                PipelineCycle.objects.filter(
                    run=run,
                    source_type=PipelineCycle.SourceType.LIVE,
                    sample_ts=sample_ts,
                )
                .order_by("cycle_index")
                .first()
            )
            if existing_live is not None:
                return Response(
                    _response_from_pipeline_cycle(existing_live, idempotent=True),
                    status=status.HTTP_200_OK,
                )

            last_cycle: PipelineCycle | None = (
                PipelineCycle.objects.filter(run=run).order_by("-cycle_index").first()
            )
            state, cycle_index = _restore_state(last_cycle, kalman_config)

            # Build the raw record with the now-known cycle_index.
            raw_record = _build_raw_record(data, row_index=cycle_index)

            # Use validate_live_record — ancillary fields are optional for
            # live ingestion; only fields that ARE present are range-checked.
            # soil_moisture=None → is_valid=False (missing) → preprocess_status="skipped".
            # A present, in-range soil_moisture → is_valid=True → preprocess_status="valid".
            validation = validate_live_record(raw_record, config=DEFAULT_VALIDATION_CONFIG)
            processed = preprocess_single(raw_record, validation)

            estimator = AdaptiveKalmanCycle(kalman_config)
            estimator._state = state  # inject reconstructed state
            cycle_result = estimator.step(processed, cycle_index=cycle_index)

            cycle_obj = map_result_to_cycle(
                cycle_result,
                run,
                slice_type=PipelineCycle.SliceType.TRAIN,
                source_type=PipelineCycle.SourceType.LIVE,
                record=processed,
            )
            try:
                cycle_obj.save()
            except IntegrityError:
                # Rare race: duplicate (run, live, sample_ts) slipped through.
                dup = (
                    PipelineCycle.objects.filter(
                        run=run,
                        source_type=PipelineCycle.SourceType.LIVE,
                        sample_ts=sample_ts,
                    )
                    .order_by("cycle_index")
                    .first()
                )
                if dup is None:
                    raise
                return Response(
                    _response_from_pipeline_cycle(dup, idempotent=True),
                    status=status.HTTP_200_OK,
                )

        logger.info(
            "Live run %d: cycle %d persisted (status=%s, adaptive=%s).",
            run_id,
            cycle_index,
            cycle_result.cycle_status,
            cycle_result.adaptive_status,
        )

        return Response(
            _live_ingest_response_body(
                cycle_index=cycle_index,
                preprocess_status=processed.preprocess_status,
                cycle_status=cycle_result.cycle_status,
                adaptive_status=cycle_result.adaptive_status,
                kf_x_posterior=cycle_result.x_posterior,
                kf_innovation=cycle_result.innovation,
            ),
            status=status.HTTP_201_CREATED,
        )
