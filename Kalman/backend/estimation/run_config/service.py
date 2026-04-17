"""
Service của RunConfig: ghi DB và quản lý vòng đời cấu hình
"""

from __future__ import annotations

import logging

from django.db import transaction

from ..models import ExperimentConfig, ExperimentRun
from .config import ConfigFrozenError, RunConfig

logger = logging.getLogger(__name__)


# ── Public API ────────────────────────────────────────────────────────────────


def create_run(
    config: RunConfig,
    *,
    run_type: str = ExperimentRun.RunType.OFFLINE_REPLAY,
    notes: str | None = None,
    owner=None,
) -> ExperimentRun:

    with transaction.atomic():
        run = ExperimentRun.objects.create(
            name=config.name,
            run_type=run_type,
            status=ExperimentRun.Status.PENDING,
            dataset_source=config.dataset_source or None,
            notes=notes,
            owner=owner,
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
    """Load và trả về "RunConfig" cho run id được truyền vào.
    """
    db_cfg = ExperimentConfig.objects.select_related("run").get(run_id=run_id)
    return RunConfig.from_experiment_config(db_cfg)


def update_config(run_id: int, config: RunConfig) -> ExperimentConfig:
    """Thay cấu hình của một run còn pending.
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

        # Giữ name / dataset_source của run đồng bộ với config.
        if run.name != config.name or run.dataset_source != (config.dataset_source or None):
            run.name = config.name
            run.dataset_source = config.dataset_source or None
            run.save(update_fields=["name", "dataset_source"])

        logger.info("Updated config for ExperimentRun pk=%d", run_id)
    return db_cfg
