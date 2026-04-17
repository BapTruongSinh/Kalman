"""
Tests for ``estimation.prediction`` — prediction adapter contract and ARX baseline.

Test strategy
-------------
- Synthetic ``ProcessedRecord`` fixtures are generated with a real AR(2) + exogenous
  process so the OLS regression matrix is well-conditioned and RMSE is meaningful.
- ``tmp_path`` (pytest fixture) is used for all artifact file I/O so no temp files
  are left behind even if an assertion fails.
- The real-data smoke tests (``TestARXAdapterRealData``) require
  ``../ARX/greenhouse_data.csv`` to exist; they call ``pytest.fail()`` when the file
  is absent so CI is not silently green without the dataset.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

from estimation.ingestion.loader import RawRecord
from estimation.ingestion.validator import ValidationResult
from estimation.ingestion.preprocessor import ProcessedRecord
from estimation.prediction import (
    ARXPredictionAdapter,
    ARXTrainConfig,
    PredictionAdapter,
    PredictionInput,
    PredictionResult,
)
from estimation.prediction.arx_adapter import (
    _build_prediction_row,
    _records_to_arrays,
    _DEFAULT_INPUT_COLS,
)

# ── Synthetic data helpers ────────────────────────────────────────────────────

_BASE_TS = datetime(2025, 1, 1, 0, 0, 0)


def _make_raw(
    idx: int,
    sm: float,
    temp: float = 22.0,
    hum: float = 70.0,
    light: float = 500.0,
    drip: float = 0.0,
    mist: float = 0.0,
    fan: float = 0.0,
) -> RawRecord:
    return RawRecord(
        timestamp=_BASE_TS + timedelta(minutes=5 * idx),
        soil_moisture=sm,
        temperature=temp,
        humidity=hum,
        light=light,
        drip=drip,
        mist=mist,
        fan=fan,
        row_index=idx,
    )


def _make_proc(
    idx: int,
    sm: float,
    temp: float = 22.0,
    hum: float = 70.0,
    light: float = 500.0,
    drip: float = 0.0,
    mist: float = 0.0,
    fan: float = 0.0,
    status: str = "valid",
) -> ProcessedRecord:
    raw = _make_raw(idx, sm, temp, hum, light, drip, mist, fan)
    val = ValidationResult(is_valid=(status == "valid"), status=status)
    return ProcessedRecord(
        raw=raw,
        validation=val,
        preprocess_status=status,
        soil_moisture=sm,
        temperature=temp,
        humidity=hum,
        light=light,
        drip=drip,
        mist=mist,
        fan=fan,
    )


def _synthetic_series(n: int = 120, seed: int = 0) -> list[ProcessedRecord]:
    """Generate *n* ProcessedRecords driven by a simple AR(2)+exogenous process.

    Parameters keep the data in a physiologically plausible range:
    SM in [50, 70], temperature varying around 22 °C, etc.
    """
    rng = np.random.default_rng(seed)
    sm = np.zeros(n)
    temp = 22.0 + 2.0 * rng.standard_normal(n)
    hum = 70.0 + 5.0 * rng.standard_normal(n)
    light = np.clip(500.0 + 50.0 * rng.standard_normal(n), 0, 2000)
    drip = (rng.uniform(0, 1, n) > 0.8).astype(float)
    mist = (rng.uniform(0, 1, n) > 0.9).astype(float)
    fan = (rng.uniform(0, 1, n) > 0.85).astype(float)

    sm[0] = 60.0
    sm[1] = 60.5
    noise = 0.05 * rng.standard_normal(n)
    for t in range(2, n):
        sm[t] = (
            0.5 * sm[t - 1]
            + 0.3 * sm[t - 2]
            + 0.1 * temp[t - 1]
            - 0.05 * hum[t - 1]
            + 0.02 * light[t - 1]
            + 0.5 * drip[t - 1]
            - 0.3 * mist[t - 1]
            + noise[t]
        )

    records = []
    for i in range(n):
        records.append(
            _make_proc(
                idx=i,
                sm=float(sm[i]),
                temp=float(temp[i]),
                hum=float(hum[i]),
                light=float(light[i]),
                drip=float(drip[i]),
                mist=float(mist[i]),
                fan=float(fan[i]),
            )
        )
    return records


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def series() -> list[ProcessedRecord]:
    return _synthetic_series(n=120)


@pytest.fixture
def trained_adapter(series: list[ProcessedRecord]) -> ARXPredictionAdapter:
    train = series[:80]
    val = series[80:100]
    adapter = ARXPredictionAdapter()
    adapter.train(train, val_records=val)
    return adapter


# ─────────────────────────────────────────────────────────────────────────────
# ARXTrainConfig
# ─────────────────────────────────────────────────────────────────────────────

class TestARXTrainConfig:
    def test_default_config(self):
        cfg = ARXTrainConfig()
        assert cfg.na == 2
        assert cfg.nb == 2
        assert cfg.nk == 1

    def test_max_lag_na2_nb2_nk1(self):
        cfg = ARXTrainConfig(na=2, nb=2, nk=1)
        # max(na, nb + nk - 1) = max(2, 2) = 2
        assert cfg.max_lag == 2

    def test_max_lag_na3_nb2_nk2(self):
        cfg = ARXTrainConfig(na=3, nb=2, nk=2)
        # max(3, 2+2-1) = max(3, 3) = 3
        assert cfg.max_lag == 3

    def test_min_history_len_equals_max_lag(self):
        cfg = ARXTrainConfig(na=2, nb=2, nk=1)
        assert cfg.min_history_len == cfg.max_lag == 2

    def test_param_names_na2_nb2_no_intercept(self):
        cfg = ARXTrainConfig(na=2, nb=2, nk=1, include_intercept=False,
                              input_cols=("Temperature",))
        names = cfg.param_names()
        assert names == ["a1", "a2", "b_Temperature_1", "b_Temperature_2"]

    def test_param_names_with_intercept(self):
        cfg = ARXTrainConfig(na=1, nb=1, nk=1, include_intercept=True,
                              input_cols=("Temperature",))
        assert "intercept" in cfg.param_names()

    def test_n_params_matches_param_names(self):
        cfg = ARXTrainConfig()
        assert cfg.n_params() == len(cfg.param_names())


# ─────────────────────────────────────────────────────────────────────────────
# ARXTrainConfig — validation
# ─────────────────────────────────────────────────────────────────────────────

class TestARXTrainConfigValidation:
    def test_na_zero_raises(self):
        with pytest.raises(ValueError, match="na must be >= 1"):
            ARXTrainConfig(na=0)

    def test_na_negative_raises(self):
        with pytest.raises(ValueError, match="na must be >= 1"):
            ARXTrainConfig(na=-1)

    def test_nb_zero_raises(self):
        with pytest.raises(ValueError, match="nb must be >= 1"):
            ARXTrainConfig(nb=0)

    def test_nk_zero_raises(self):
        with pytest.raises(ValueError, match="nk must be >= 1"):
            ARXTrainConfig(nk=0)

    def test_empty_input_cols_raises(self):
        with pytest.raises(ValueError, match="input_cols must not be empty"):
            ARXTrainConfig(input_cols=())

    def test_unknown_input_col_raises(self):
        with pytest.raises(ValueError, match="Unknown input column"):
            ARXTrainConfig(input_cols=("NotAColumn",))

    def test_unknown_output_col_raises(self):
        with pytest.raises(ValueError, match="Unknown output_col"):
            ARXTrainConfig(output_col="NotAColumn")

    def test_valid_config_does_not_raise(self):
        cfg = ARXTrainConfig(na=1, nb=1, nk=1, input_cols=("Temperature",))
        assert cfg.na == 1

    def test_default_config_is_valid(self):
        cfg = ARXTrainConfig()
        assert cfg.na == 2


# ─────────────────────────────────────────────────────────────────────────────
# PredictionInput / PredictionResult
# ─────────────────────────────────────────────────────────────────────────────

class TestPredictionInputResult:
    def test_prediction_result_ok(self):
        r = PredictionResult(value=60.5, status="ok", model_kind="arx")
        assert r.value == pytest.approx(60.5)
        assert r.status == "ok"
        assert r.reason == ""

    def test_prediction_result_unavailable(self):
        r = PredictionResult(value=None, status="unavailable",
                              model_kind="arx", reason="not trained")
        assert r.value is None
        assert r.status == "unavailable"

    def test_prediction_result_is_frozen(self):
        r = PredictionResult(value=1.0, status="ok", model_kind="arx")
        with pytest.raises((AttributeError, TypeError)):
            r.value = 2.0  # type: ignore[misc]

    def test_prediction_input_default_empty(self):
        inp = PredictionInput()
        assert inp.history == []

    def test_prediction_input_stores_records(self):
        recs = [_make_proc(i, 60.0 + i) for i in range(3)]
        inp = PredictionInput(history=recs)
        assert len(inp.history) == 3


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

class TestInternalHelpers:
    def test_records_to_arrays_shape(self, series):
        cfg = ARXTrainConfig(na=2, nb=2, nk=1)
        x, y = _records_to_arrays(series[:20], cfg)
        n_eff = 20 - cfg.max_lag
        assert x.shape == (n_eff, cfg.n_params())
        assert y.shape == (n_eff,)

    def test_records_to_arrays_raises_too_short(self):
        cfg = ARXTrainConfig(na=3, nb=3, nk=1)
        short = [_make_proc(i, 60.0) for i in range(cfg.max_lag)]
        with pytest.raises(ValueError, match="Not enough records"):
            _records_to_arrays(short, cfg)

    def test_build_prediction_row_length(self):
        cfg = ARXTrainConfig(na=2, nb=2, nk=1)
        recs = [_make_proc(i, 60.0 + 0.1 * i) for i in range(5)]
        row = _build_prediction_row(recs, cfg)
        assert len(row) == cfg.n_params()

    def test_build_prediction_row_ar_values(self):
        """AR part of the row must be the last na soil_moisture values."""
        cfg = ARXTrainConfig(na=2, nb=1, nk=1, input_cols=("Temperature",))
        recs = [
            _make_proc(0, sm=50.0, temp=20.0),
            _make_proc(1, sm=55.0, temp=21.0),
            _make_proc(2, sm=60.0, temp=22.0),
        ]
        row = _build_prediction_row(recs, cfg)
        # a1 term = y[-1] = 60.0, a2 term = y[-2] = 55.0
        assert row[0] == pytest.approx(60.0)
        assert row[1] == pytest.approx(55.0)


# ─────────────────────────────────────────────────────────────────────────────
# ARXPredictionAdapter — training
# ─────────────────────────────────────────────────────────────────────────────

class TestARXAdapterTrain:
    def test_not_trained_initially(self):
        adapter = ARXPredictionAdapter()
        assert not adapter.is_trained

    def test_is_trained_after_train(self, series):
        adapter = ARXPredictionAdapter()
        adapter.train(series[:80])
        assert adapter.is_trained

    def test_train_returns_summary_keys(self, series):
        adapter = ARXPredictionAdapter()
        summary = adapter.train(series[:80])
        for key in ("model_kind", "na", "nb", "nk", "n_params", "n_train",
                    "sigma2", "train_metrics"):
            assert key in summary

    def test_train_summary_model_kind(self, series):
        adapter = ARXPredictionAdapter()
        summary = adapter.train(series[:80])
        assert summary["model_kind"] == "arx"

    def test_train_metrics_present(self, series):
        adapter = ARXPredictionAdapter()
        adapter.train(series[:80])
        m = adapter.train_metrics
        assert m is not None
        assert "rmse" in m and "mae" in m and "r2" in m

    def test_val_metrics_present_when_val_provided(self, series):
        adapter = ARXPredictionAdapter()
        adapter.train(series[:80], val_records=series[80:100])
        assert adapter.val_metrics is not None
        assert adapter.val_metrics["rmse"] >= 0.0

    def test_val_metrics_none_without_val(self, series):
        adapter = ARXPredictionAdapter()
        adapter.train(series[:80])
        assert adapter.val_metrics is None

    def test_train_raises_too_few_records(self):
        adapter = ARXPredictionAdapter()
        tiny = [_make_proc(i, 60.0) for i in range(2)]  # need > max_lag=2
        with pytest.raises(ValueError):
            adapter.train(tiny)

    def test_train_rmse_is_finite(self, series):
        adapter = ARXPredictionAdapter()
        adapter.train(series[:80])
        assert np.isfinite(adapter.train_metrics["rmse"])

    def test_model_kind_and_min_history_len(self):
        adapter = ARXPredictionAdapter(ARXTrainConfig(na=3, nb=2, nk=2))
        assert adapter.model_kind == "arx"
        assert adapter.min_history_len == 3  # max(3, 2+2-1) = 3


# ─────────────────────────────────────────────────────────────────────────────
# ARXPredictionAdapter — prediction
# ─────────────────────────────────────────────────────────────────────────────

class TestARXAdapterPredict:
    def test_predict_ok_when_trained(self, trained_adapter, series):
        inp = PredictionInput(history=series[78:80])  # last 2 of train slice
        result = trained_adapter.predict(inp)
        assert result.status == "ok"
        assert result.value is not None
        assert np.isfinite(result.value)
        assert result.model_kind == "arx"

    def test_predict_value_in_plausible_range(self, trained_adapter, series):
        inp = PredictionInput(history=series[78:80])
        result = trained_adapter.predict(inp)
        # Soil_Moisture should be in some wide range for a trained model
        assert -500.0 < result.value < 500.0

    def test_predict_unavailable_when_not_trained(self, series):
        adapter = ARXPredictionAdapter()
        inp = PredictionInput(history=series[:5])
        result = adapter.predict(inp)
        assert result.status == "unavailable"
        assert result.value is None
        assert "not trained" in result.reason.lower()

    def test_predict_unavailable_history_too_short(self, trained_adapter, series):
        inp = PredictionInput(history=series[:1])  # need 2, only 1
        result = trained_adapter.predict(inp)
        assert result.status == "unavailable"
        assert result.value is None
        assert "short" in result.reason.lower()

    def test_predict_unavailable_empty_history(self, trained_adapter):
        result = trained_adapter.predict(PredictionInput(history=[]))
        assert result.status == "unavailable"

    def test_predict_unavailable_none_soil_moisture(self, trained_adapter, series):
        rec_with_none = ProcessedRecord(
            raw=series[79].raw,
            validation=series[79].validation,
            preprocess_status="skipped",
            soil_moisture=None,
            temperature=22.0,
            humidity=70.0,
            light=500.0,
            drip=0.0,
            mist=0.0,
            fan=0.0,
        )
        inp = PredictionInput(history=[series[78], rec_with_none])
        result = trained_adapter.predict(inp)
        assert result.status == "unavailable"
        assert "None" in result.reason

    def test_predict_never_raises(self, trained_adapter):
        """predict() must not raise under any circumstances."""
        try:
            result = trained_adapter.predict(PredictionInput(history=[]))
        except Exception as exc:  # noqa: BLE001
            pytest.fail(f"predict() raised unexpectedly: {exc}")
        assert result is not None

    def test_predict_never_raises_none_inp(self, trained_adapter):
        """predict(None) must return PredictionResult, not raise AttributeError."""
        try:
            result = trained_adapter.predict(None)  # type: ignore[arg-type]
        except Exception as exc:  # noqa: BLE001
            pytest.fail(f"predict(None) raised: {exc}")
        assert result is not None
        assert result.status == "error"

    def test_predict_never_raises_none_history(self, trained_adapter):
        """predict(PredictionInput(history=None)) must not raise TypeError."""
        inp = PredictionInput.__new__(PredictionInput)
        object.__setattr__(inp, "history", None)  # bypass type-hint for test
        try:
            result = trained_adapter.predict(inp)
        except Exception as exc:  # noqa: BLE001
            pytest.fail(f"predict(history=None) raised: {exc}")
        assert result is not None
        assert result.status in ("unavailable", "error")

    def test_predict_never_raises_malformed_history_object(self, trained_adapter):
        """predict() must not raise when history is a non-sequence (e.g. object())."""
        class BadInput:
            history = object()  # has no __len__

        try:
            result = trained_adapter.predict(BadInput())  # type: ignore[arg-type]
        except Exception as exc:  # noqa: BLE001
            pytest.fail(f"predict(malformed history) raised: {exc}")
        assert result is not None
        assert result.status == "error"

    def test_predict_never_raises_len_raises(self, trained_adapter):
        """predict() must not raise when len(history) itself raises."""
        class LenRaisesInput:
            class _BadList:
                def __len__(self):
                    raise RuntimeError("len boom")
            history = _BadList()

        try:
            result = trained_adapter.predict(LenRaisesInput())  # type: ignore[arg-type]
        except Exception as exc:  # noqa: BLE001
            pytest.fail(f"predict(len raises) raised: {exc}")
        assert result is not None
        assert result.status == "error"


# ─────────────────────────────────────────────────────────────────────────────
# ARXPredictionAdapter — artifact save/load
# ─────────────────────────────────────────────────────────────────────────────

class TestARXAdapterArtifact:
    def test_save_raises_when_not_trained(self, tmp_path):
        adapter = ARXPredictionAdapter()
        with pytest.raises(RuntimeError, match="Cannot save"):
            adapter.save_artifact(tmp_path / "model.json")

    def test_save_creates_file(self, trained_adapter, tmp_path):
        path = tmp_path / "arx.json"
        trained_adapter.save_artifact(path)
        assert path.exists()

    def test_save_native_format_has_adapter_version(self, trained_adapter, tmp_path):
        path = tmp_path / "arx.json"
        trained_adapter.save_artifact(path)
        data = json.loads(path.read_text())
        assert data.get("adapter_version") == "1"
        assert data.get("model") == "ARX"

    def test_roundtrip_is_trained(self, trained_adapter, tmp_path):
        path = tmp_path / "arx.json"
        trained_adapter.save_artifact(path)
        loaded = ARXPredictionAdapter.load_artifact(path)
        assert loaded.is_trained

    def test_roundtrip_same_prediction(self, trained_adapter, series, tmp_path):
        path = tmp_path / "arx.json"
        trained_adapter.save_artifact(path)
        loaded = ARXPredictionAdapter.load_artifact(path)

        inp = PredictionInput(history=series[78:80])
        r_orig = trained_adapter.predict(inp)
        r_load = loaded.predict(inp)
        assert r_orig.status == "ok"
        assert r_load.status == "ok"
        assert r_orig.value == pytest.approx(r_load.value, rel=1e-9)

    def test_roundtrip_config_preserved(self, tmp_path, series):
        cfg = ARXTrainConfig(na=3, nb=1, nk=1, include_intercept=True,
                              input_cols=("Temperature",))
        adapter = ARXPredictionAdapter(cfg)
        adapter.train(series[:100])
        path = tmp_path / "arx3.json"
        adapter.save_artifact(path)
        loaded = ARXPredictionAdapter.load_artifact(path)
        assert loaded.train_config.na == 3
        assert loaded.train_config.nb == 1
        assert loaded.train_config.include_intercept is True

    def test_load_raises_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            ARXPredictionAdapter.load_artifact(tmp_path / "nonexistent.json")

    def test_load_raises_invalid_format(self, tmp_path):
        bad = tmp_path / "bad.json"
        bad.write_text('{"foo": "bar"}', encoding="utf-8")
        with pytest.raises(ValueError, match="Unrecognised artifact format"):
            ARXPredictionAdapter.load_artifact(bad)

    def test_load_pipeline_format(self, tmp_path):
        """load_artifact() must accept arx_pipeline.save_artifact() output."""
        pipeline_payload = {
            "model": "ARX",
            "model_config": {
                "na": 2,
                "nb": 2,
                "nk": 1,
                "include_intercept": False,
                "input_cols": list(_DEFAULT_INPUT_COLS),
                "output_col": "Soil_Moisture",
            },
            "theta_hat": [0.5, 0.3, 0.1, 0.05, 0.01, 0.01,
                          0.01, 0.01, 0.01, 0.01, 0.01, 0.01,
                          0.01, 0.01],
            "sigma2": 0.25,
            "slices": {
                "train": {"metrics_1step": {"RMSE": 0.5, "MAE": 0.4, "R2": 0.9}},
                "val": {"metrics_1step": {"RMSE": 0.6, "MAE": 0.45, "R2": 0.85}},
            },
        }
        path = tmp_path / "pipeline.json"
        path.write_text(json.dumps(pipeline_payload), encoding="utf-8")
        adapter = ARXPredictionAdapter.load_artifact(path)
        assert adapter.is_trained
        assert adapter.train_config.na == 2
        assert adapter.train_metrics is not None
        assert adapter.val_metrics is not None

    def test_load_pipeline_prefers_best_candidate(self, tmp_path):
        """best_candidate config and theta must override top-level when present."""
        pipeline_payload = {
            "model": "ARX",
            "model_config": {"na": 2, "nb": 2, "nk": 1, "include_intercept": False,
                              "input_cols": list(_DEFAULT_INPUT_COLS),
                              "output_col": "Soil_Moisture"},
            "theta_hat": [0.0] * 14,
            "sigma2": 1.0,
            "slices": {},
            "best_candidate": {
                "model_config": {"na": 3, "nb": 1, "nk": 1,
                                 "include_intercept": False,
                                 "input_cols": list(_DEFAULT_INPUT_COLS),
                                 "output_col": "Soil_Moisture"},
                "theta_hat": [0.6, 0.2, 0.1, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                "sigma2": 0.2,
                "val": {"metrics_1step": {"RMSE": 0.4, "MAE": 0.3, "R2": 0.92}},
            },
        }
        path = tmp_path / "best.json"
        path.write_text(json.dumps(pipeline_payload), encoding="utf-8")
        adapter = ARXPredictionAdapter.load_artifact(path)
        # Must use best_candidate config (na=3) not top-level (na=2)
        assert adapter.train_config.na == 3
        assert adapter.val_metrics is not None
        assert adapter.val_metrics["rmse"] == pytest.approx(0.4)

    def test_load_pipeline_best_candidate_uses_best_sigma2(self, tmp_path):
        """sigma2 loaded from best_candidate must match best, not top-level."""
        top_sigma2 = 1.0
        best_sigma2 = 0.07
        pipeline_payload = {
            "model": "ARX",
            "model_config": {"na": 2, "nb": 2, "nk": 1, "include_intercept": False,
                              "input_cols": list(_DEFAULT_INPUT_COLS),
                              "output_col": "Soil_Moisture"},
            "theta_hat": [0.0] * 14,
            "sigma2": top_sigma2,
            "slices": {},
            "best_candidate": {
                "model_config": {"na": 2, "nb": 2, "nk": 1,
                                 "include_intercept": False,
                                 "input_cols": list(_DEFAULT_INPUT_COLS),
                                 "output_col": "Soil_Moisture"},
                "theta_hat": [0.0] * 14,
                "sigma2": best_sigma2,
                "val": {"metrics_1step": {"RMSE": 0.3, "MAE": 0.2, "R2": 0.95}},
            },
        }
        path = tmp_path / "best_sigma.json"
        path.write_text(json.dumps(pipeline_payload), encoding="utf-8")
        adapter = ARXPredictionAdapter.load_artifact(path)
        # Must use best_candidate sigma2, not top-level sigma2
        assert adapter._sigma2 == pytest.approx(best_sigma2)
        assert adapter._sigma2 != pytest.approx(top_sigma2)

    def test_load_native_theta_length_mismatch_raises(self, tmp_path):
        """load_artifact() must raise ValueError when theta length != config.n_params()."""
        bad_payload = {
            "adapter_version": "1",
            "model": "ARX",
            "model_config": {
                "na": 2, "nb": 2, "nk": 1, "include_intercept": False,
                "input_cols": list(_DEFAULT_INPUT_COLS),
                "output_col": "Soil_Moisture",
            },
            # correct n_params = 2 + 6*2 = 14; deliberately wrong
            "theta_hat": [0.1, 0.2, 0.3],
            "sigma2": 0.25,
        }
        path = tmp_path / "bad_theta.json"
        path.write_text(json.dumps(bad_payload), encoding="utf-8")
        with pytest.raises(ValueError, match="theta has"):
            ARXPredictionAdapter.load_artifact(path)

    def test_load_pipeline_theta_length_mismatch_raises(self, tmp_path):
        """Pipeline-format load must also raise on theta length mismatch."""
        bad_payload = {
            "model": "ARX",
            "model_config": {
                "na": 2, "nb": 2, "nk": 1, "include_intercept": False,
                "input_cols": list(_DEFAULT_INPUT_COLS),
                "output_col": "Soil_Moisture",
            },
            "theta_hat": [0.1],  # should be 14 params
            "sigma2": 0.25,
        }
        path = tmp_path / "bad_pipeline_theta.json"
        path.write_text(json.dumps(bad_payload), encoding="utf-8")
        with pytest.raises(ValueError, match="theta has"):
            ARXPredictionAdapter.load_artifact(path)


# ─────────────────────────────────────────────────────────────────────────────
# Public API contracts
# ─────────────────────────────────────────────────────────────────────────────

class TestPublicAPI:
    def test_all_symbols_importable(self):
        from estimation.prediction import (  # noqa: F401
            ARXPredictionAdapter,
            ARXTrainConfig,
            PredictionAdapter,
            PredictionInput,
            PredictionResult,
        )

    def test_arx_adapter_is_prediction_adapter_subclass(self):
        assert issubclass(ARXPredictionAdapter, PredictionAdapter)

    def test_all_in___all__(self):
        from estimation import prediction
        for name in [
            "PredictionInput",
            "PredictionResult",
            "PredictionAdapter",
            "ARXTrainConfig",
            "ARXPredictionAdapter",
        ]:
            assert name in prediction.__all__, f"{name} missing from __all__"

    def test_prediction_adapter_is_abstract(self):
        with pytest.raises(TypeError):
            PredictionAdapter()  # type: ignore[abstract]


# ─────────────────────────────────────────────────────────────────────────────
# Real-data smoke tests — require ../ARX/greenhouse_data.csv
# ─────────────────────────────────────────────────────────────────────────────

_GREENHOUSE_CSV = Path(__file__).parents[4] / "ARX" / "greenhouse_data.csv"


class TestARXAdapterRealData:
    """Smoke tests against the actual greenhouse dataset.

    These tests call ``pytest.fail()`` if the CSV is absent so CI is not
    silently green when the dataset has not been committed or generated.
    """

    def _load_split(self):
        if not _GREENHOUSE_CSV.exists():
            pytest.fail(
                f"greenhouse_data.csv not found at {_GREENHOUSE_CSV}. "
                "Generate it with 'python ARX/arx_pipeline.py' or "
                "provide the file before running real-data tests."
            )
        from estimation.ingestion import (
            load_csv,
            split_chronological,
            validate_batch,
            apply_preprocessing,
        )
        raw = load_csv(_GREENHOUSE_CSV)
        split = split_chronological(raw)
        validations = validate_batch(split.train)
        processed = apply_preprocessing(split.train, validations)
        v_validations = validate_batch(split.validation)
        v_processed = apply_preprocessing(split.validation, v_validations)
        return processed, v_processed

    def test_train_on_real_data(self):
        train, val = self._load_split()
        adapter = ARXPredictionAdapter()
        summary = adapter.train(train, val_records=val)
        assert adapter.is_trained
        assert summary["train_metrics"]["rmse"] >= 0.0
        assert summary["val_metrics"]["rmse"] >= 0.0

    def test_predict_on_real_history(self):
        train, val = self._load_split()
        adapter = ARXPredictionAdapter()
        adapter.train(train)
        # Use last min_history_len records from train as history window
        n = adapter.min_history_len
        inp = PredictionInput(history=train[-n:])
        result = adapter.predict(inp)
        assert result.status == "ok"
        assert result.value is not None
        assert np.isfinite(result.value)

    def test_load_existing_arx_artifact_and_predict(self):
        """load_artifact() from the pre-built arx_model.json must produce a real result."""
        artifact_path = _GREENHOUSE_CSV.parent / "arx_model.json"
        if not artifact_path.exists():
            pytest.fail(
                f"arx_model.json not found at {artifact_path}. "
                "Run 'python ARX/arx_pipeline.py' to generate it."
            )
        adapter = ARXPredictionAdapter.load_artifact(artifact_path)
        assert adapter.is_trained

        # Build a small history window from the real data to smoke-test predict
        from estimation.ingestion import load_csv, validate_batch, apply_preprocessing
        raw = load_csv(_GREENHOUSE_CSV)
        n = adapter.min_history_len
        val_batch = validate_batch(raw[:n])
        processed = apply_preprocessing(raw[:n], val_batch)
        result = adapter.predict(PredictionInput(history=processed))
        assert result.status == "ok"
        assert np.isfinite(result.value)
