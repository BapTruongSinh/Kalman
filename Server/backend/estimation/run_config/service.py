"""
Service của RunConfig: ghi DB và quản lý vòng đời cấu hình.

Trách nhiệm
-----------
1. ``create_run``: ghi ``ExperimentRun`` + ``ExperimentConfig`` từ
   ``RunConfig`` trong một transaction.
2. ``load_config``: dựng lại ``RunConfig`` từ run id đã có.
3. ``update_config``: thay config của một run còn *pending*; khi run đã bắt đầu
   thì raise ``ConfigFrozenError``.

Mô hình quyền ở v1
------------------
Không cho đổi cấu hình khi ``ExperimentRun.status`` không còn ``"pending"``.
Đây là invariant cứng của tầng service; v1 chưa có cơ chế phân quyền theo role.
Ràng buộc được ghi ở ``config.py`` và enforce tại đây để Task #007 hoặc caller
nào cố mutate run đang chạy sẽ nhận lỗi rõ ràng thay vì ghi đè âm thầm.
"""

from __future__ import annotations

import logging

from django.db import transaction

from ..models import ExperimentConfig, ExperimentRun, Greenhouse
from kalman.run_config import ConfigFrozenError, RunConfig

logger = logging.getLogger(__name__)


# ── Public API ────────────────────────────────────────────────────────────────


def create_run(
    config: RunConfig,
    *,
    notes: str | None = None,
    greenhouse: Greenhouse | None = None,
) -> ExperimentRun:
    """Tạo ``ExperimentRun`` và snapshot ``ExperimentConfig`` trong một transaction.

    Dòng ``ExperimentConfig`` lưu đúng giá trị tham số để sau này có thể tái
    lập run. ``raw_config_json`` lưu snapshot JSON đầy đủ để dễ tương thích khi
    schema phát triển.

    Parameters
    ----------
    config:
        Instance ``RunConfig`` đã validate.
    notes:
        Ghi chú dạng text tùy chọn lưu trên dòng run.
    greenhouse:
        Nhà kính mà run này theo dõi. Quyền ingest suy ra qua ``greenhouse.owner``.

    Returns
    -------
    ExperimentRun
        Dòng run mới tạo, có ``status="pending"``.
    """
    if greenhouse is None:
        raise ValueError("create_run requires a greenhouse")

    with transaction.atomic():
        run = ExperimentRun.objects.create(
            name=config.name,
            run_type=ExperimentRun.RunType.LIVE,
            status=ExperimentRun.Status.PENDING,
            dataset_source=config.dataset_source or None,
            notes=notes,
            greenhouse=greenhouse,
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
            raw_config_json=config.to_json(),
        )
        logger.info("Created ExperimentRun pk=%d name=%r", run.pk, run.name)
    return run


def load_config(run_id: int) -> RunConfig:
    """Load và trả về ``RunConfig`` cho run id được truyền vào.

    Raises
    ------
    ExperimentRun.DoesNotExist
        Nếu không có run với ``pk=run_id``.
    ExperimentConfig.DoesNotExist
        Nếu run tồn tại nhưng chưa có dòng config tương ứng.
    """
    db_cfg = ExperimentConfig.objects.select_related("run").get(run_id=run_id)
    return RunConfig.from_experiment_config(db_cfg)


def update_config(run_id: int, config: RunConfig) -> ExperimentConfig:
    """Thay cấu hình của một run còn *pending*.

    Dòng ``ExperimentConfig`` được ghi đè và ``raw_config_json`` được refresh.
    Chỉ run có ``status="pending"`` mới được cập nhật.

    Parameters
    ----------
    run_id:
        Primary key của ``ExperimentRun`` cần cập nhật.
    config:
        ``RunConfig`` mới cần lưu.

    Returns
    -------
    ExperimentConfig
        Dòng config đã cập nhật.

    Raises
    ------
    ConfigFrozenError
        Nếu trạng thái run không phải ``"pending"``.
    ExperimentRun.DoesNotExist
        Nếu không có run với ``pk=run_id``.
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
        db_cfg.raw_config_json = config.to_json()
        db_cfg.save()

        # Giữ name / dataset_source của run đồng bộ với config.
        if run.name != config.name or run.dataset_source != (config.dataset_source or None):
            run.name = config.name
            run.dataset_source = config.dataset_source or None
            run.save(update_fields=["name", "dataset_source"])

        logger.info("Updated config for ExperimentRun pk=%d", run_id)
    return db_cfg
