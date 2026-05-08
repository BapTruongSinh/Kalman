"""Tests for live-only RunConfig persistence."""

import pytest
from django.db import IntegrityError

from estimation.models import ExperimentConfig, ExperimentRun
from estimation.run_config import ConfigFrozenError, RunConfig, create_run, load_config, update_config


def test_run_config_validates_kalman() -> None:
    cfg = RunConfig(name="live", Q=0.1)
    assert cfg.to_kalman_config().Q == 0.1

    with pytest.raises(ValueError):
        RunConfig(Q=-1.0)


def test_run_config_json_ignores_removed_offline_keys() -> None:
    raw = (
        '{"name":"old","train_ratio":0.6,"val_ratio":0.2,"test_ratio":0.2,'
        '"arx_na":2,"arx_nb":2,"arx_nk":1,"arx_input_cols":["Temperature"],'
        '"preprocessing_policy":"keep_last"}'
    )
    cfg = RunConfig.from_json(raw)
    assert cfg.name == "old"
    assert not hasattr(cfg, "train_ratio")
    assert not hasattr(cfg, "preprocessing_policy")


@pytest.mark.django_db
def test_create_run_defaults_to_live() -> None:
    run = create_run(RunConfig(name="device-run"))
    assert run.run_type == ExperimentRun.RunType.LIVE
    cfg = ExperimentConfig.objects.get(run=run)
    assert cfg.raw_config_json


@pytest.mark.django_db
def test_load_and_update_config() -> None:
    run = create_run(RunConfig(name="initial", Q=0.05))
    updated = update_config(run.pk, RunConfig(name="updated", Q=0.2))
    assert updated.Q == 0.2
    assert load_config(run.pk).name == "updated"


@pytest.mark.django_db
def test_update_config_rejects_started_run() -> None:
    run = create_run(RunConfig(name="running"))
    run.status = ExperimentRun.Status.RUNNING
    run.save(update_fields=["status"])

    with pytest.raises(ConfigFrozenError):
        update_config(run.pk, RunConfig(name="blocked"))


@pytest.mark.django_db
def test_db_rejects_legacy_run_type_when_bypassing_service() -> None:
    with pytest.raises(IntegrityError):
        ExperimentRun.objects.create(name="legacy", run_type="offline_replay")
