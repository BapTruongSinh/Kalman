"""
RunConfig service — persistence and lifecycle management.

Responsibilities
----------------
1. ``create_run``  — atomically write ``ExperimentRun`` + ``ExperimentConfig``
   from a ``RunConfig``.
2. ``load_config`` — reconstruct a ``RunConfig`` from an existing run id.
3. ``update_config`` — replace the config of a *pending* run; raises
   ``ConfigFrozenError`` once the run has started.

v1 authorization model
-----------------------
Configuration changes are blocked once ``ExperimentRun.status`` is no longer
``"pending"``.  This is a hard service-layer invariant; there is no role-based
auth mechanism in v1.  The restriction is documented in ``config.py`` and
enforced here so Task #007 / any caller that tries to mutate a live run
receives a clear error rather than a silent overwrite.
"""

from __future__ import annotations

import logging

from django.db import transaction

from ..models import ExperimentConfig, ExperimentRun
from .config import ConfigFrozenError, RunConfig

logger = logging.getLogger(__name__)


# ── Public API ─────────────────────────────────────────────────────────────────


def create_run(
    config: RunConfig,
    *,
    run_type: str = ExperimentRun.RunType.OFFLINE_REPLAY,
    notes: str | None = None,
) -> ExperimentRun:
    """Atomically create an ``ExperimentRun`` + its ``ExperimentConfig`` snapshot.

    The ``ExperimentConfig`` row captures the exact parameter values so the run
    can be reproduced later.  ``raw_config_json`` stores the full JSON snapshot
    for forward-compatibility.

    Parameters
    ----------
    config:
        Validated ``RunConfig`` instance.
    run_type:
        ``ExperimentRun.RunType`` choice string; defaults to ``"offline_replay"``.
    notes:
        Optional free-text annotation stored on the run row.

    Returns
    -------
    ExperimentRun
        The newly created (``status="pending"``) run row.
    """
    with transaction.atomic():
        run = ExperimentRun.objects.create(
            name=config.name,
            run_type=run_type,
            status=ExperimentRun.Status.PENDING,
            dataset_source=config.dataset_source or None,
            notes=notes,
        )
        ExperimentConfig.objects.create(
            run=run,
            x0=config.x0,
            P0=config.P0,
            Q=config.Q,
            R0=config.R0,
            R_min=config.R_min,
            R_max=config.R_max,
            alpha=config.alpha,
            train_ratio=config.train_ratio,
            val_ratio=config.val_ratio,
            test_ratio=config.test_ratio,
            arx_na=config.arx_na,
            arx_nb=config.arx_nb,
            arx_nk=config.arx_nk,
            preprocessing_policy=config.preprocessing_policy,
            raw_config_json=config.to_json(),
        )
        logger.info("Created ExperimentRun pk=%d name=%r", run.pk, run.name)
    return run


def load_config(run_id: int) -> RunConfig:
    """Load and return the ``RunConfig`` for the given run id.

    Raises
    ------
    ExperimentRun.DoesNotExist
        If no run with ``pk=run_id`` exists.
    ExperimentConfig.DoesNotExist
        If the run exists but has no associated config row.
    """
    db_cfg = ExperimentConfig.objects.select_related("run").get(run_id=run_id)
    return RunConfig.from_experiment_config(db_cfg)


def update_config(run_id: int, config: RunConfig) -> ExperimentConfig:
    """Replace the configuration of a *pending* run.

    The ``ExperimentConfig`` row is overwritten and ``raw_config_json`` is
    refreshed.  Only runs with ``status="pending"`` may be updated.

    Parameters
    ----------
    run_id:
        Primary key of the target ``ExperimentRun``.
    config:
        New ``RunConfig`` to persist.

    Returns
    -------
    ExperimentConfig
        The updated row.

    Raises
    ------
    ConfigFrozenError
        If the run status is not ``"pending"``.
    ExperimentRun.DoesNotExist
        If no run with ``pk=run_id`` exists.
    """
    with transaction.atomic():
        run = ExperimentRun.objects.select_for_update().get(pk=run_id)
        if run.status != ExperimentRun.Status.PENDING:
            raise ConfigFrozenError(
                f"Cannot update config for run {run_id}: "
                f"status is {run.status!r}, must be 'pending'. "
                "Configuration is immutable once a run has started."
            )
        db_cfg = ExperimentConfig.objects.get(run=run)
        db_cfg.x0 = config.x0
        db_cfg.P0 = config.P0
        db_cfg.Q = config.Q
        db_cfg.R0 = config.R0
        db_cfg.R_min = config.R_min
        db_cfg.R_max = config.R_max
        db_cfg.alpha = config.alpha
        db_cfg.train_ratio = config.train_ratio
        db_cfg.val_ratio = config.val_ratio
        db_cfg.test_ratio = config.test_ratio
        db_cfg.arx_na = config.arx_na
        db_cfg.arx_nb = config.arx_nb
        db_cfg.arx_nk = config.arx_nk
        db_cfg.preprocessing_policy = config.preprocessing_policy
        db_cfg.raw_config_json = config.to_json()
        db_cfg.save()

        # Keep run name / dataset_source in sync.
        if run.name != config.name or run.dataset_source != (config.dataset_source or None):
            run.name = config.name
            run.dataset_source = config.dataset_source or None
            run.save(update_fields=["name", "dataset_source"])

        logger.info("Updated config for ExperimentRun pk=%d", run_id)
    return db_cfg
