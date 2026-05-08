"""Tests for artifact-only ARX prediction."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from estimation.ingestion import ProcessedRecord, RawRecord, ValidationResult
from estimation.prediction import ARXArtifactConfig, ARXPredictionAdapter, PredictionInput

_ARTIFACT = Path(__file__).parents[4] / "ARX" / "arx_model.json"


def _processed(i: int, sm: float = 50.0) -> ProcessedRecord:
    raw = RawRecord(
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=i),
        soil_moisture=sm + i * 0.1,
        temperature=25.0 + i * 0.01,
        humidity=70.0,
        light=100.0,
        drip=0.0,
        fan=0.0,
        mist=0.0,
        row_index=i,
    )
    return ProcessedRecord(
        raw=raw,
        validation=ValidationResult(is_valid=True, status="valid", reason="ok"),
        preprocess_status="valid",
        soil_moisture=raw.soil_moisture,
        temperature=raw.temperature,
        humidity=raw.humidity,
        light=raw.light,
        drip=raw.drip,
        fan=raw.fan,
        mist=raw.mist,
    )


def test_artifact_config_validates_orders_and_columns() -> None:
    cfg = ARXArtifactConfig(na=2, nb=2, nk=1, input_cols=("Temperature",))
    assert cfg.min_history_len == 2

    with pytest.raises(ValueError):
        ARXArtifactConfig(na=0)
    with pytest.raises(ValueError):
        ARXArtifactConfig(input_cols=("Unknown",))


def test_load_repo_arx_artifact() -> None:
    adapter = ARXPredictionAdapter.load_artifact(_ARTIFACT)
    assert adapter.model_kind == "arx"
    assert adapter.is_trained is True
    assert adapter.min_history_len >= 1


def test_predict_returns_unavailable_when_history_too_short() -> None:
    adapter = ARXPredictionAdapter.load_artifact(_ARTIFACT)
    result = adapter.predict(PredictionInput(history=[]))
    assert result.status == "unavailable"
    assert result.value is None


def test_predict_from_loaded_artifact_never_raises() -> None:
    adapter = ARXPredictionAdapter.load_artifact(_ARTIFACT)
    history = [_processed(i) for i in range(adapter.min_history_len)]
    result = adapter.predict(PredictionInput(history=history))
    assert result.status == "ok"
    assert isinstance(result.value, float)


def test_missing_artifact_raises_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        ARXPredictionAdapter.load_artifact(tmp_path / "missing.json")
