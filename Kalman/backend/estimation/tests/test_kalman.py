"""Tests for one-step Adaptive Kalman runtime."""

from datetime import datetime, timezone

from estimation.ingestion import ProcessedRecord, RawRecord, ValidationResult
from estimation.kalman import AdaptiveKalmanCycle, KalmanConfig
from estimation.prediction import PredictionAdapter, PredictionInput, PredictionResult


def _record(sm: float | None, status: str = "valid") -> ProcessedRecord:
    raw = RawRecord(
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        soil_moisture=sm,
        temperature=25.0,
        humidity=70.0,
        light=100.0,
        drip=0.0,
        fan=0.0,
        mist=0.0,
        row_index=0,
    )
    return ProcessedRecord(
        raw=raw,
        validation=ValidationResult(
            is_valid=sm is not None,
            status="valid" if sm is not None else "missing",
            reason="ok",
        ),
        preprocess_status=status,
        soil_moisture=sm,
        temperature=raw.temperature,
        humidity=raw.humidity,
        light=raw.light,
        drip=raw.drip,
        fan=raw.fan,
        mist=raw.mist,
    )


class FakeAdapter(PredictionAdapter):
    model_kind = "fake"
    is_trained = True
    min_history_len = 0

    def predict(self, inp: PredictionInput) -> PredictionResult:
        return PredictionResult(value=40.0, status="ok", model_kind="fake")

    @classmethod
    def load_artifact(cls, path):
        return cls()


def test_step_updates_state_with_measurement() -> None:
    est = AdaptiveKalmanCycle(KalmanConfig(x0=50.0, Q=0.05, R0=1.0))
    result = est.step(_record(52.0), cycle_index=0)
    assert result.cycle_status == "ok"
    assert result.adaptive_status == "R_updated"
    assert result.x_posterior != 50.0
    assert est.state.step == 1


def test_step_skips_missing_measurement() -> None:
    est = AdaptiveKalmanCycle(KalmanConfig(x0=50.0))
    result = est.step(_record(None, status="skipped"), cycle_index=0)
    assert result.cycle_status == "skipped_no_measurement"
    assert result.K is None


def test_adapter_prediction_becomes_prior() -> None:
    est = AdaptiveKalmanCycle(KalmanConfig(x0=50.0), adapter=FakeAdapter())
    result = est.step(_record(42.0), cycle_index=0)
    assert result.arx_predicted == 40.0
    assert result.x_prior == 40.0


def test_step_never_raises_on_bad_record() -> None:
    est = AdaptiveKalmanCycle(KalmanConfig())
    result = est.step(object(), cycle_index=3)  # type: ignore[arg-type]
    assert result.cycle_status == "error"
    assert result.error_message
