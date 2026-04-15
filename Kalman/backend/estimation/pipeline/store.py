"""
Pipeline storage layer (Task #007).

Responsibilities
----------------
* Map ``CycleResult`` → an unsaved ``PipelineCycle`` ORM instance, including
  the ``kf_`` column prefix translation and optional raw sensor columns from the
  paired ``ProcessedRecord``.
* Bulk-insert batches of ``PipelineCycle`` records efficiently.
* Transition ``ExperimentRun`` status through its lifecycle:
  PENDING → RUNNING → COMPLETED | FAILED | ABORTED.

Design constraints
------------------
* ``map_result_to_cycle`` is a **pure function** (no DB calls).  All field
  translation happens here; no logic leaks into the bulk-insert path.
* ``bulk_save_cycles`` issues a single ``bulk_create`` per batch — never
  one INSERT per row.
* Status transitions use a conditional ``QuerySet.update`` (single UPDATE
  query) to avoid race conditions; they raise ``RunStateError`` when the
  pre-condition is not met.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Sequence

from ..ingestion.preprocessor import ProcessedRecord
from ..kalman import CycleResult
from ..models import ExperimentRun, PipelineCycle

logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────


def ingest_dedupe_key_for_persist(
    run_id: int,
    source_type: str,
    *,
    cycle_index: int,
    sample_ts: datetime | None = None,
) -> str:
    """Build a MySQL-safe unique key for ``PipelineCycle.ingest_dedupe_key``.

    Partial ``UNIQUE`` indexes (``WHERE source_type='live'``) are not emitted on
    some MySQL configurations, so we use an explicit string key instead.

    * **live** — ``live|{run_id}|{UTC ISO-8601 timestamp}`` — at most one live
      row per run per sensor timestamp (idempotent retries).
    * **csv_replay / mysql_replay** — ``csv|…`` / ``mysql|…`` plus zero-padded
      ``cycle_index`` — CSV rows may share ``sample_ts`` within a run.
    """
    if source_type == PipelineCycle.SourceType.LIVE:
        if sample_ts is None:
            raise ValueError("ingest_dedupe_key_for_persist: sample_ts required for live")
        ts = sample_ts
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        else:
            ts = ts.astimezone(timezone.utc)
        return f"live|{run_id}|{ts.isoformat()}"
    if source_type == PipelineCycle.SourceType.CSV_REPLAY:
        return f"csv|{run_id}|{cycle_index:010d}"
    if source_type == PipelineCycle.SourceType.MYSQL_REPLAY:
        return f"mysql|{run_id}|{cycle_index:010d}"
    raise ValueError(f"unsupported source_type {source_type!r}")


def _require_choice(value: str, choices: type, field: str) -> str:
    """Validate *value* against a TextChoices class; raise ``ValueError`` if invalid.

    This provides a storage-boundary guard so that callers cannot silently
    write enum garbage into the traceability table.  The corresponding
    ``CheckConstraint``s on the model back-stop this at the DB level.
    """
    valid = {v for v, _ in choices.choices}
    if value not in valid:
        raise ValueError(
            f"Invalid {field} value {value!r}. "
            f"Expected one of {sorted(valid)}."
        )
    return value


# ── Exception ─────────────────────────────────────────────────────────────────


class RunStateError(RuntimeError):
    """Raised when a run status transition is invalid.

    For example: calling ``begin_run`` on a run that is already ``RUNNING``,
    or calling ``end_run`` on a run that is still ``PENDING``.
    """


# ── Field mapping ─────────────────────────────────────────────────────────────

# Terminal statuses that ``end_run`` accepts.
_TERMINAL_STATUSES = frozenset({
    ExperimentRun.Status.COMPLETED,
    ExperimentRun.Status.FAILED,
    ExperimentRun.Status.ABORTED,
})


def map_result_to_cycle(
    result: CycleResult,
    run: ExperimentRun,
    slice_type: str,
    source_type: str = PipelineCycle.SourceType.CSV_REPLAY,
    record: ProcessedRecord | None = None,
) -> PipelineCycle:
    """Map a ``CycleResult`` to an unsaved ``PipelineCycle`` ORM instance.

    This is a **pure function** — no database access.  Pair with
    :func:`bulk_save_cycles` to persist.

    Field mapping
    -------------
    CycleResult field        → PipelineCycle column
    ──────────────────────────────────────────────────
    timestamp                → sample_ts
    cycle_index              → cycle_index
    raw_soil_moisture        → raw_soil_moisture
    preprocess_status        → preprocess_status
    arx_predicted            → arx_predicted
    x_prior                  → kf_x_prior
    P_prior                  → kf_P_prior
    innovation               → kf_innovation
    R                        → kf_R
    K                        → kf_K
    x_posterior              → kf_x_posterior
    P_posterior              → kf_P_posterior
    adaptive_status          → adaptive_status
    cycle_status             → cycle_status
    error_message            → error_message
    latency_ms               → latency_ms

    Run-level metadata is supplied by the caller:
    run, slice_type, source_type → PipelineCycle columns of the same name.

    All enum fields (``slice_type``, ``source_type``, ``preprocess_status``,
    ``adaptive_status``, ``cycle_status``) are validated against their
    ``TextChoices`` before the instance is constructed.  Unrecognised values
    raise ``ValueError`` immediately — before any DB write.

    Parameters
    ----------
    result:
        Output of ``AdaptiveKalmanCycle.step()``.
    run:
        Parent ``ExperimentRun`` (must already be saved in the DB).
    slice_type:
        One of ``"train"``, ``"validation"``, ``"test"``.
    source_type:
        One of ``"csv_replay"``, ``"mysql_replay"``, ``"live"``
        (defaults to ``"csv_replay"``).
    record:
        Optional ``ProcessedRecord`` that produced this result.  When supplied,
        the raw sensor readings (temperature, humidity, light, drip, mist, fan)
        are copied to the corresponding ``raw_*`` columns for full traceability.
    """
    # ── Enum validation (storage-boundary guard) ──────────────────────────────
    _require_choice(slice_type, PipelineCycle.SliceType, "slice_type")
    _require_choice(source_type, PipelineCycle.SourceType, "source_type")
    _require_choice(result.preprocess_status, PipelineCycle.PreprocessStatus, "preprocess_status")
    _require_choice(result.adaptive_status, PipelineCycle.AdaptiveStatus, "adaptive_status")
    _require_choice(result.cycle_status, PipelineCycle.CycleStatus, "cycle_status")

    raw = record.raw if record is not None else None

    dedupe_key = ingest_dedupe_key_for_persist(
        run.pk,
        source_type,
        cycle_index=result.cycle_index,
        sample_ts=result.timestamp,
    )

    return PipelineCycle(
        run=run,
        sample_ts=result.timestamp,
        cycle_index=result.cycle_index,
        ingest_dedupe_key=dedupe_key,
        slice_type=slice_type,
        source_type=source_type,
        # ── Raw measurements ──────────────────────────────────────────────────
        raw_soil_moisture=result.raw_soil_moisture,
        raw_temperature=raw.temperature if raw is not None else None,
        raw_humidity=raw.humidity if raw is not None else None,
        raw_light=raw.light if raw is not None else None,
        raw_drip=raw.drip if raw is not None else None,
        raw_mist=raw.mist if raw is not None else None,
        raw_fan=raw.fan if raw is not None else None,
        # ── Preprocessing outcome ─────────────────────────────────────────────
        preprocess_status=result.preprocess_status,
        # ── ARX prediction ────────────────────────────────────────────────────
        arx_predicted=result.arx_predicted,
        # ── Kalman internals (kf_ prefix per schema) ──────────────────────────
        kf_x_prior=result.x_prior,
        kf_P_prior=result.P_prior,
        kf_innovation=result.innovation,
        kf_R=result.R,
        kf_K=result.K,
        kf_x_posterior=result.x_posterior,
        kf_P_posterior=result.P_posterior,
        # ── Adaptive estimator outcome ────────────────────────────────────────
        adaptive_status=result.adaptive_status,
        # ── Cycle outcome ─────────────────────────────────────────────────────
        cycle_status=result.cycle_status,
        error_message=result.error_message,
        # ── Performance ───────────────────────────────────────────────────────
        latency_ms=result.latency_ms,
    )


# ── Persistence ───────────────────────────────────────────────────────────────


def bulk_save_cycles(
    cycles: Sequence[PipelineCycle],
    *,
    batch_size: int = 500,
) -> int:
    """Persist a sequence of unsaved ``PipelineCycle`` instances.

    Uses a single ``bulk_create`` call (batched at *batch_size*) for
    throughput.  Do **not** call per-row ``save()`` inside hot loops.

    Parameters
    ----------
    cycles:
        Unsaved ``PipelineCycle`` objects, typically produced by
        :func:`map_result_to_cycle`.
    batch_size:
        Number of rows per INSERT statement (default 500).

    Returns
    -------
    int
        Number of rows inserted.
    """
    if not cycles:
        return 0
    created = PipelineCycle.objects.bulk_create(
        list(cycles),
        batch_size=batch_size,
    )
    n = len(created)
    logger.debug("bulk_save_cycles: inserted %d PipelineCycle rows", n)
    return n


# ── Run lifecycle ─────────────────────────────────────────────────────────────


def begin_run(run: ExperimentRun) -> None:
    """Transition *run* from ``PENDING`` → ``RUNNING``.

    Uses a conditional ``QuerySet.update`` so the transition is atomic even
    under concurrent access.  The local *run* object is refreshed from the
    database after a successful update.

    Raises
    ------
    RunStateError
        If *run* is not currently ``PENDING`` (e.g. already ``RUNNING`` or
        ``COMPLETED``).
    """
    updated = ExperimentRun.objects.filter(
        pk=run.pk,
        status=ExperimentRun.Status.PENDING,
    ).update(
        status=ExperimentRun.Status.RUNNING,
        started_at=datetime.now(tz=timezone.utc),
    )
    if updated == 0:
        # Re-read current status for a helpful error message.
        current = ExperimentRun.objects.values_list("status", flat=True).get(pk=run.pk)
        raise RunStateError(
            f"Cannot begin run #{run.pk}: current status is {current!r}, "
            f"expected {ExperimentRun.Status.PENDING!r}."
        )
    run.refresh_from_db()
    logger.info("Run #%d started (status=running).", run.pk)


def end_run(run: ExperimentRun, status: str) -> None:
    """Transition *run* from ``RUNNING`` to a terminal status.

    Acceptable terminal statuses: ``"completed"``, ``"failed"``,
    ``"aborted"``.  The local *run* object is refreshed after a successful
    update.

    Parameters
    ----------
    run:
        The ``ExperimentRun`` to finalise.
    status:
        Target terminal status (must be ``"completed"``, ``"failed"``, or
        ``"aborted"``).

    Raises
    ------
    ValueError
        If *status* is not a recognised terminal status.
    RunStateError
        If *run* is not currently ``RUNNING``.
    """
    if status not in _TERMINAL_STATUSES:
        raise ValueError(
            f"Invalid terminal status {status!r}. "
            f"Expected one of {sorted(_TERMINAL_STATUSES)}."
        )
    updated = ExperimentRun.objects.filter(
        pk=run.pk,
        status=ExperimentRun.Status.RUNNING,
    ).update(
        status=status,
        completed_at=datetime.now(tz=timezone.utc),
    )
    if updated == 0:
        current = ExperimentRun.objects.values_list("status", flat=True).get(pk=run.pk)
        raise RunStateError(
            f"Cannot end run #{run.pk}: current status is {current!r}, "
            f"expected {ExperimentRun.Status.RUNNING!r}."
        )
    run.refresh_from_db()
    logger.info("Run #%d ended (status=%s).", run.pk, status)
