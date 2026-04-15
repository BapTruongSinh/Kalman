"""
Tests for ``estimation.run_config``.

Coverage areas
--------------
* RunConfig validation — good values, every possible bad value, NaN/Inf.
* arx_input_cols coercion — list/other sequence normalised to immutable tuple.
* JSON round-trip — to_json() / from_json() with full defaults and custom values.
* Sub-config extraction — to_kalman_config(), to_arx_train_config().
* ORM round-trip — from_experiment_config() via a stub object.
* Service layer (DB) — create_run, load_config, update_config, ConfigFrozenError.
* Acceptance criterion — replay reproducibility: same config → same KalmanConfig/ARXTrainConfig.
* Import isolation — ``from estimation.run_config import RunConfig`` must not require Django.
"""

from __future__ import annotations

import math
import json
import subprocess
import sys
import pytest
from unittest.mock import MagicMock, patch

# ── Module under test ─────────────────────────────────────────────────────────
from estimation.run_config import (
    ConfigFrozenError,
    RunConfig,
    create_run,
    load_config,
    update_config,
)
from estimation.kalman import KalmanConfig
from estimation.prediction import ARXTrainConfig


# ── Helpers ───────────────────────────────────────────────────────────────────

def _default_config(**overrides) -> RunConfig:
    """Return a valid RunConfig with optional field overrides."""
    defaults = dict(
        name="test_run",
        dataset_source="/data/greenhouse.csv",
        x0=30.0,
        P0=2.0,
        Q=0.1,
        R0=2.0,
        R_min=0.1,
        R_max=20.0,
        alpha=0.9,
        train_ratio=0.60,
        val_ratio=0.20,
        test_ratio=0.20,
        arx_na=2,
        arx_nb=2,
        arx_nk=1,
        arx_input_cols=("Temperature", "Humidity", "Light"),
        preprocessing_policy="keep_last",
    )
    defaults.update(overrides)
    return RunConfig(**defaults)


# ── TestRunConfigValidation ───────────────────────────────────────────────────

class TestRunConfigValidation:
    """Valid construction and field-level validation."""

    def test_default_construction(self):
        cfg = RunConfig()
        assert cfg.name == "unnamed_run"
        assert cfg.x0 == 0.0
        assert cfg.P0 == 1.0
        assert cfg.Q == 0.05
        assert cfg.R0 == 1.0
        assert cfg.R_min == 0.05
        assert cfg.R_max == 25.0
        assert cfg.alpha == 0.95
        assert math.isclose(cfg.train_ratio + cfg.val_ratio + cfg.test_ratio, 1.0)
        assert cfg.arx_na == 2
        assert cfg.arx_nb == 2
        assert cfg.arx_nk == 1
        assert cfg.preprocessing_policy == "keep_last"

    def test_custom_valid_construction(self):
        cfg = _default_config()
        assert cfg.name == "test_run"
        assert cfg.x0 == 30.0

    def test_Q_zero_is_valid(self):
        cfg = _default_config(Q=0.0)
        assert cfg.Q == 0.0

    # ── Kalman field validation ───────────────────────────────────────────────

    def test_P0_nonpositive_raises(self):
        with pytest.raises(ValueError, match="P0"):
            _default_config(P0=0.0)

    def test_Q_negative_raises(self):
        with pytest.raises(ValueError, match="Q"):
            _default_config(Q=-0.01)

    def test_R0_nonpositive_raises(self):
        with pytest.raises(ValueError, match="R0"):
            _default_config(R0=0.0)

    def test_R_min_not_less_than_R_max_raises(self):
        with pytest.raises(ValueError):
            _default_config(R_min=5.0, R_max=5.0)

    def test_R0_outside_bounds_raises(self):
        with pytest.raises(ValueError, match="R0"):
            _default_config(R_min=0.1, R0=0.05, R_max=20.0)

    def test_alpha_above_one_raises(self):
        with pytest.raises(ValueError, match="alpha"):
            _default_config(alpha=1.1)

    def test_alpha_negative_raises(self):
        with pytest.raises(ValueError, match="alpha"):
            _default_config(alpha=-0.1)

    # ── NaN / Inf rejection ───────────────────────────────────────────────────

    @pytest.mark.parametrize("field_name,bad_val", [
        ("x0",    float("nan")),
        ("x0",    float("inf")),
        ("x0",    float("-inf")),
        ("P0",    float("nan")),
        ("Q",     float("inf")),
        ("R0",    float("nan")),
        ("R_min", float("inf")),
        ("R_max", float("nan")),
        ("alpha", float("nan")),
    ])
    def test_non_finite_kalman_field_raises(self, field_name, bad_val):
        with pytest.raises(ValueError):
            _default_config(**{field_name: bad_val})

    @pytest.mark.parametrize("field_name,bad_val", [
        ("train_ratio", float("nan")),
        ("val_ratio",   float("inf")),
        ("test_ratio",  float("-inf")),
    ])
    def test_non_finite_ratio_raises(self, field_name, bad_val):
        with pytest.raises(ValueError):
            _default_config(**{field_name: bad_val})

    # ── Split ratio validation ────────────────────────────────────────────────

    def test_ratios_not_summing_to_one_raises(self):
        with pytest.raises(ValueError, match="sum"):
            RunConfig(train_ratio=0.5, val_ratio=0.3, test_ratio=0.3)

    def test_zero_ratio_raises(self):
        with pytest.raises(ValueError):
            RunConfig(train_ratio=0.0, val_ratio=0.5, test_ratio=0.5)

    def test_negative_ratio_raises(self):
        with pytest.raises(ValueError):
            RunConfig(train_ratio=-0.1, val_ratio=0.6, test_ratio=0.5)

    # ── ARX field validation ──────────────────────────────────────────────────

    def test_arx_na_less_than_one_raises(self):
        with pytest.raises(ValueError, match="na"):
            _default_config(arx_na=0)

    def test_arx_nb_less_than_one_raises(self):
        with pytest.raises(ValueError, match="nb"):
            _default_config(arx_nb=0)

    def test_arx_nk_less_than_one_raises(self):
        with pytest.raises(ValueError, match="nk"):
            _default_config(arx_nk=0)

    def test_unknown_arx_input_col_raises(self):
        with pytest.raises(ValueError, match="Unknown input column"):
            _default_config(arx_input_cols=("Temperature", "INVALID_COL"))

    def test_empty_arx_input_cols_raises(self):
        with pytest.raises(ValueError, match="empty"):
            _default_config(arx_input_cols=())

    # ── Preprocessing policy validation ──────────────────────────────────────

    def test_invalid_preprocessing_policy_raises(self):
        with pytest.raises(ValueError, match="preprocessing_policy"):
            _default_config(preprocessing_policy="unknown_policy")

    @pytest.mark.parametrize("policy", ["keep_last", "interpolate", "skip"])
    def test_all_valid_preprocessing_policies(self, policy):
        cfg = _default_config(preprocessing_policy=policy)
        assert cfg.preprocessing_policy == policy


# ── TestRunConfigSubConfigExtraction ─────────────────────────────────────────

class TestRunConfigSubConfigExtraction:
    """to_kalman_config() and to_arx_train_config() return correct objects."""

    def test_to_kalman_config_values(self):
        cfg = _default_config(x0=25.0, P0=3.0, Q=0.02, R0=1.5, R_min=0.05, R_max=15.0, alpha=0.8)
        kc = cfg.to_kalman_config()
        assert isinstance(kc, KalmanConfig)
        assert kc.x0 == 25.0
        assert kc.P0 == 3.0
        assert kc.Q == 0.02
        assert kc.R0 == 1.5
        assert kc.R_min == 0.05
        assert kc.R_max == 15.0
        assert kc.alpha == 0.8

    def test_to_arx_train_config_values(self):
        cfg = _default_config(arx_na=3, arx_nb=4, arx_nk=2,
                               arx_input_cols=("Temperature", "Humidity"))
        ac = cfg.to_arx_train_config()
        assert isinstance(ac, ARXTrainConfig)
        assert ac.na == 3
        assert ac.nb == 4
        assert ac.nk == 2
        assert ac.input_cols == ("Temperature", "Humidity")

    def test_default_config_sub_configs_are_valid(self):
        cfg = RunConfig()
        kc = cfg.to_kalman_config()
        ac = cfg.to_arx_train_config()
        assert isinstance(kc, KalmanConfig)
        assert isinstance(ac, ARXTrainConfig)

    def test_replay_reproducibility(self):
        """Replaying with a saved config must produce identical sub-configs."""
        cfg_orig = _default_config(Q=0.03, arx_na=3, arx_nk=2)
        serialised = cfg_orig.to_json()
        cfg_restored = RunConfig.from_json(serialised)
        assert cfg_restored.to_kalman_config() == cfg_orig.to_kalman_config()
        assert cfg_restored.to_arx_train_config() == cfg_orig.to_arx_train_config()


# ── TestRunConfigJSON ─────────────────────────────────────────────────────────

class TestRunConfigJSON:
    """JSON round-trip: to_json() / from_json()."""

    def test_round_trip_defaults(self):
        cfg = RunConfig()
        cfg2 = RunConfig.from_json(cfg.to_json())
        assert cfg == cfg2

    def test_round_trip_custom(self):
        cfg = _default_config()
        cfg2 = RunConfig.from_json(cfg.to_json())
        assert cfg == cfg2

    def test_json_contains_all_fields(self):
        cfg = RunConfig()
        d = json.loads(cfg.to_json())
        for field_name in (
            "name", "dataset_source",
            "x0", "P0", "Q", "R0", "R_min", "R_max", "alpha",
            "train_ratio", "val_ratio", "test_ratio",
            "arx_na", "arx_nb", "arx_nk", "arx_input_cols",
            "preprocessing_policy",
        ):
            assert field_name in d, f"Missing field {field_name!r} in JSON"

    def test_arx_input_cols_is_list_in_json(self):
        cfg = RunConfig()
        d = json.loads(cfg.to_json())
        assert isinstance(d["arx_input_cols"], list)

    def test_from_json_restores_tuple(self):
        cfg = RunConfig()
        cfg2 = RunConfig.from_json(cfg.to_json())
        assert isinstance(cfg2.arx_input_cols, tuple)

    def test_from_json_invalid_json_raises_value_error(self):
        with pytest.raises(ValueError, match="Invalid JSON"):
            RunConfig.from_json("{not valid json")

    def test_from_json_unknown_field_raises_value_error(self):
        cfg = RunConfig()
        d = json.loads(cfg.to_json())
        d["unknown_field"] = 123
        with pytest.raises(ValueError, match="unexpected fields"):
            RunConfig.from_json(json.dumps(d))

    def test_from_json_invalid_value_raises_value_error(self):
        cfg = RunConfig()
        d = json.loads(cfg.to_json())
        d["P0"] = -1.0  # invalid: must be > 0
        with pytest.raises(ValueError):
            RunConfig.from_json(json.dumps(d))

    def test_from_json_non_object_raises_value_error(self):
        with pytest.raises(ValueError, match="must be an object"):
            RunConfig.from_json("[]")

    def test_from_json_null_arx_input_cols_raises_value_error(self):
        cfg = RunConfig()
        d = json.loads(cfg.to_json())
        d["arx_input_cols"] = None
        with pytest.raises(ValueError, match="arx_input_cols"):
            RunConfig.from_json(json.dumps(d))


# ── TestRunConfigFromExperimentConfig ─────────────────────────────────────────

class TestRunConfigFromExperimentConfig:
    """from_experiment_config() reconstructs correctly from ORM stub."""

    def _make_stub(self, **overrides) -> MagicMock:
        """Return a minimal mock that looks like an ExperimentConfig row."""
        run_mock = MagicMock()
        run_mock.name = "stub_run"
        run_mock.dataset_source = "/data/test.csv"

        raw_json_cfg = _default_config(name="stub_run", dataset_source="/data/test.csv")
        row = MagicMock()
        row.run = run_mock
        row.x0 = raw_json_cfg.x0
        row.P0 = raw_json_cfg.P0
        row.Q = raw_json_cfg.Q
        row.R0 = raw_json_cfg.R0
        row.R_min = raw_json_cfg.R_min
        row.R_max = raw_json_cfg.R_max
        row.alpha = raw_json_cfg.alpha
        row.train_ratio = raw_json_cfg.train_ratio
        row.val_ratio = raw_json_cfg.val_ratio
        row.test_ratio = raw_json_cfg.test_ratio
        row.arx_na = raw_json_cfg.arx_na
        row.arx_nb = raw_json_cfg.arx_nb
        row.arx_nk = raw_json_cfg.arx_nk
        row.preprocessing_policy = raw_json_cfg.preprocessing_policy
        row.raw_config_json = raw_json_cfg.to_json()
        for k, v in overrides.items():
            setattr(row, k, v)
        return row

    def test_round_trip_via_orm_stub(self):
        original = _default_config()
        stub = self._make_stub()
        restored = RunConfig.from_experiment_config(stub)
        assert restored.x0 == original.x0
        assert restored.P0 == original.P0
        assert restored.Q == original.Q
        assert restored.arx_na == original.arx_na
        assert restored.preprocessing_policy == original.preprocessing_policy

    def test_arx_input_cols_from_json(self):
        cfg = _default_config(arx_input_cols=("Temperature", "Humidity"))
        stub = self._make_stub(raw_config_json=cfg.to_json())
        restored = RunConfig.from_experiment_config(stub)
        assert restored.arx_input_cols == ("Temperature", "Humidity")

    def test_fallback_to_default_arx_cols_when_json_missing(self):
        stub = self._make_stub(raw_config_json="{}")
        from estimation.prediction.arx_adapter import _DEFAULT_INPUT_COLS
        restored = RunConfig.from_experiment_config(stub)
        assert restored.arx_input_cols == _DEFAULT_INPUT_COLS

    def test_fallback_to_default_arx_cols_on_bad_json(self):
        stub = self._make_stub(raw_config_json="{invalid}")
        from estimation.prediction.arx_adapter import _DEFAULT_INPUT_COLS
        restored = RunConfig.from_experiment_config(stub)
        assert restored.arx_input_cols == _DEFAULT_INPUT_COLS

    def test_name_from_run(self):
        stub = self._make_stub()
        stub.run.name = "my_experiment"
        restored = RunConfig.from_experiment_config(stub)
        assert restored.name == "my_experiment"

    def test_dataset_source_from_run(self):
        stub = self._make_stub()
        stub.run.dataset_source = "/custom/path.csv"
        restored = RunConfig.from_experiment_config(stub)
        assert restored.dataset_source == "/custom/path.csv"


# ── TestRunConfigService (DB tests via Django TestCase) ───────────────────────

from django.test import TestCase


class TestCreateRun(TestCase):
    """create_run() persists both ExperimentRun and ExperimentConfig rows."""

    def test_creates_run_and_config_rows(self):
        from estimation.models import ExperimentConfig, ExperimentRun
        cfg = _default_config(name="db_test_run")
        run = create_run(cfg)
        assert ExperimentRun.objects.filter(pk=run.pk).exists()
        assert ExperimentConfig.objects.filter(run=run).exists()

    def test_run_starts_as_pending(self):
        cfg = _default_config()
        run = create_run(cfg)
        assert run.status == "pending"

    def test_run_name_matches_config(self):
        cfg = _default_config(name="named_run_test")
        run = create_run(cfg)
        run.refresh_from_db()
        assert run.name == "named_run_test"

    def test_config_values_persisted(self):
        from estimation.models import ExperimentConfig
        cfg = _default_config(Q=0.07, alpha=0.88, arx_na=3)
        run = create_run(cfg)
        db_cfg = ExperimentConfig.objects.get(run=run)
        assert db_cfg.Q == pytest.approx(0.07)
        assert db_cfg.alpha == pytest.approx(0.88)
        assert db_cfg.arx_na == 3

    def test_raw_config_json_is_valid_json(self):
        from estimation.models import ExperimentConfig
        cfg = _default_config()
        run = create_run(cfg)
        db_cfg = ExperimentConfig.objects.get(run=run)
        parsed = json.loads(db_cfg.raw_config_json)
        assert parsed["Q"] == pytest.approx(cfg.Q)

    def test_dataset_source_stored(self):
        cfg = _default_config(dataset_source="/data/custom.csv")
        run = create_run(cfg)
        run.refresh_from_db()
        assert run.dataset_source == "/data/custom.csv"

    def test_run_type_custom(self):
        from django.contrib.auth import get_user_model

        from estimation.models import ExperimentRun

        cfg = _default_config()
        user = get_user_model().objects.create_user(username="live_owner_svc", password="x")
        run = create_run(cfg, run_type=ExperimentRun.RunType.LIVE, owner=user)
        assert run.run_type == "live"

    def test_notes_stored(self):
        cfg = _default_config()
        run = create_run(cfg, notes="some notes")
        run.refresh_from_db()
        assert run.notes == "some notes"


class TestLoadConfig(TestCase):
    """load_config() reconstructs RunConfig from DB."""

    def test_load_config_round_trip(self):
        cfg = _default_config(x0=15.0, Q=0.03)
        run = create_run(cfg)
        restored = load_config(run.pk)
        assert isinstance(restored, RunConfig)
        assert restored.x0 == pytest.approx(15.0)
        assert restored.Q == pytest.approx(0.03)

    def test_load_config_kalman_config_matches(self):
        cfg = _default_config(alpha=0.92, R_max=30.0)
        run = create_run(cfg)
        restored = load_config(run.pk)
        assert restored.to_kalman_config() == cfg.to_kalman_config()

    def test_load_config_arx_config_matches(self):
        cfg = _default_config(arx_na=3, arx_nb=4, arx_nk=2,
                               arx_input_cols=("Temperature", "Humidity"))
        run = create_run(cfg)
        restored = load_config(run.pk)
        assert restored.to_arx_train_config() == cfg.to_arx_train_config()

    def test_load_config_nonexistent_run_raises(self):
        from estimation.models import ExperimentConfig
        with pytest.raises(ExperimentConfig.DoesNotExist):
            load_config(run_id=999999)

    def test_load_preprocessing_policy(self):
        cfg = _default_config(preprocessing_policy="interpolate")
        run = create_run(cfg)
        restored = load_config(run.pk)
        assert restored.preprocessing_policy == "interpolate"


class TestUpdateConfig(TestCase):
    """update_config() replaces a pending run's config and blocks non-pending."""

    def test_update_pending_run_succeeds(self):
        cfg = _default_config(Q=0.05)
        run = create_run(cfg)
        new_cfg = _default_config(Q=0.10, name="updated_run")
        update_config(run.pk, new_cfg)
        restored = load_config(run.pk)
        assert restored.Q == pytest.approx(0.10)

    def test_update_refreshes_raw_json(self):
        from estimation.models import ExperimentConfig
        cfg = _default_config()
        run = create_run(cfg)
        new_cfg = _default_config(alpha=0.80)
        update_config(run.pk, new_cfg)
        db_cfg = ExperimentConfig.objects.get(run=run)
        d = json.loads(db_cfg.raw_config_json)
        assert d["alpha"] == pytest.approx(0.80)

    def test_update_syncs_run_name(self):
        cfg = _default_config(name="old_name")
        run = create_run(cfg)
        new_cfg = _default_config(name="new_name")
        update_config(run.pk, new_cfg)
        run.refresh_from_db()
        assert run.name == "new_name"

    def test_update_nonpending_run_raises_config_frozen(self):
        from estimation.models import ExperimentRun
        cfg = _default_config()
        run = create_run(cfg)
        run.status = ExperimentRun.Status.RUNNING
        run.save()
        with pytest.raises(ConfigFrozenError):
            update_config(run.pk, _default_config(Q=0.99))

    def test_update_completed_run_raises_config_frozen(self):
        from estimation.models import ExperimentRun
        cfg = _default_config()
        run = create_run(cfg)
        run.status = ExperimentRun.Status.COMPLETED
        run.save()
        with pytest.raises(ConfigFrozenError):
            update_config(run.pk, _default_config())

    def test_update_nonexistent_run_raises(self):
        with pytest.raises(Exception):
            update_config(run_id=999999, config=_default_config())


# ── TestConfigFrozenError ─────────────────────────────────────────────────────

class TestConfigFrozenError:
    def test_is_runtime_error(self):
        err = ConfigFrozenError("test message")
        assert isinstance(err, RuntimeError)
        assert "test message" in str(err)


# ── TestRunConfigImmutability ─────────────────────────────────────────────────

class TestRunConfigImmutability:
    """Frozen dataclass must not allow attribute mutation."""

    def test_direct_mutation_raises(self):
        cfg = RunConfig()
        with pytest.raises((TypeError, AttributeError)):
            cfg.Q = 0.99  # type: ignore[misc]

    def test_direct_mutation_x0_raises(self):
        cfg = RunConfig()
        with pytest.raises((TypeError, AttributeError)):
            cfg.x0 = 99.0  # type: ignore[misc]


# ── TestArxInputColsCoercion ──────────────────────────────────────────────────

class TestArxInputColsCoercion:
    """arx_input_cols is always stored as an immutable tuple.

    Regression guard for: passing a list allowed in-place mutation even though
    the dataclass is frozen, because frozen only prevents field *rebinding*,
    not mutation of the referenced mutable object.
    """

    def test_list_input_stored_as_tuple(self):
        cfg = RunConfig(arx_input_cols=["Temperature", "Humidity"])
        assert isinstance(cfg.arx_input_cols, tuple)
        assert cfg.arx_input_cols == ("Temperature", "Humidity")

    def test_list_cannot_be_mutated_after_construction(self):
        original = ["Temperature", "Humidity"]
        cfg = RunConfig(arx_input_cols=original)
        # Mutate the original list — stored value must be unaffected.
        original.append("Light")
        assert cfg.arx_input_cols == ("Temperature", "Humidity")
        assert len(cfg.arx_input_cols) == 2

    def test_stored_tuple_has_no_append(self):
        cfg = RunConfig(arx_input_cols=["Temperature"])
        assert not hasattr(cfg.arx_input_cols, "append")

    def test_probe_list_append_does_not_mutate_config(self):
        """Exact probe from the finding report."""
        cfg = RunConfig(arx_input_cols=["Temperature"])
        with pytest.raises(AttributeError):
            cfg.arx_input_cols.append("Humidity")  # type: ignore[attr-defined]

    def test_tuple_input_stays_tuple(self):
        cols = ("Temperature", "Humidity", "Light")
        cfg = RunConfig(arx_input_cols=cols)
        assert isinstance(cfg.arx_input_cols, tuple)
        assert cfg.arx_input_cols == cols

    def test_json_round_trip_preserves_tuple_type(self):
        cfg = RunConfig(arx_input_cols=["Temperature", "Humidity"])
        cfg2 = RunConfig.from_json(cfg.to_json())
        assert isinstance(cfg2.arx_input_cols, tuple)

    def test_from_experiment_config_stub_returns_tuple(self):
        """from_experiment_config always yields a tuple, not a list."""
        stub = MagicMock()
        stub.run.name = "t"
        stub.run.dataset_source = ""
        stub.x0 = 0.0; stub.P0 = 1.0; stub.Q = 0.05
        stub.R0 = 1.0; stub.R_min = 0.05; stub.R_max = 25.0; stub.alpha = 0.95
        stub.train_ratio = 0.6; stub.val_ratio = 0.2; stub.test_ratio = 0.2
        stub.arx_na = 2; stub.arx_nb = 2; stub.arx_nk = 1
        stub.preprocessing_policy = "keep_last"
        # JSON contains a list (as produced by json.dumps on a list)
        stub.raw_config_json = '{"arx_input_cols": ["Temperature", "Humidity"]}'
        cfg = RunConfig.from_experiment_config(stub)
        assert isinstance(cfg.arx_input_cols, tuple)

    def test_none_input_raises_value_error(self):
        with pytest.raises(ValueError, match="arx_input_cols"):
            RunConfig(arx_input_cols=None)  # type: ignore[arg-type]


# ── TestImportIsolation ───────────────────────────────────────────────────────

class TestImportIsolation:
    """``from estimation.run_config import RunConfig`` must not require Django.

    This is verified by running a fresh Python subprocess with no
    DJANGO_SETTINGS_MODULE set.  The import should succeed and print 'ok'.
    """

    _BACKEND_DIR = str(
        __import__("pathlib").Path(__file__).resolve().parents[2]
    )  # …/Kalman/backend

    def _run_isolated(self, code: str) -> subprocess.CompletedProcess:
        """Run *code* in a clean subprocess without Django settings."""
        env = {
            k: v
            for k, v in __import__("os").environ.items()
            if k != "DJANGO_SETTINGS_MODULE"
        }
        return subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            cwd=self._BACKEND_DIR,
            env=env,
        )

    def test_run_config_importable_without_django(self):
        """Pure RunConfig import must succeed with no DJANGO_SETTINGS_MODULE."""
        result = self._run_isolated(
            "from estimation.run_config import RunConfig, ConfigFrozenError; print('ok')"
        )
        assert result.returncode == 0, (
            f"Import failed.\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert "ok" in result.stdout

    def test_run_config_construction_without_django(self):
        """RunConfig() construction must work outside Django context."""
        result = self._run_isolated(
            "from estimation.run_config import RunConfig\n"
            "cfg = RunConfig(name='t', Q=0.1)\n"
            "assert cfg.Q == 0.1\n"
            "print('ok')"
        )
        assert result.returncode == 0, (
            f"Construction failed.\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert "ok" in result.stdout

    def test_service_functions_not_imported_eagerly(self):
        """Service names must NOT appear in the module dict before first access."""
        result = self._run_isolated(
            "import sys\n"
            "from estimation.run_config import RunConfig\n"
            "import estimation.run_config as m\n"
            "assert 'create_run' not in m.__dict__, "
            "    'create_run imported eagerly — Django coupling not fixed'\n"
            "print('ok')"
        )
        assert result.returncode == 0, (
            f"Eager import check failed.\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
