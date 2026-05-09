# Kalman Algorithm Support Package

`Kalman/` is now a pure Python package for Adaptive Kalman estimation support code. It must not contain Django, database models, migrations, API views, or dashboard code.

Scope note: this package is intentionally algorithm-only, not strictly filter-only. It includes the pure data contracts and adapters the filter needs at runtime: ingestion validation/preprocessing, ARX prediction adapter contract, Adaptive Kalman cycle, pure metrics, and run config dataclass. Server integration, persistence, auth, API, and dashboard stay in `Green-House/Green-House-master`.

Public imports:

```python
from kalman.filter import AdaptiveKalmanCycle, KalmanConfig
from kalman.ingestion import RawRecord, validate_live_record, preprocess_single
from kalman.prediction import ARXPredictionAdapter, PredictionResult
from kalman.evaluation import compute_metrics
```

Run package checks from the repo root:

```powershell
python -m pytest Kalman\tests -q
python -m compileall -q Kalman\kalman
```
