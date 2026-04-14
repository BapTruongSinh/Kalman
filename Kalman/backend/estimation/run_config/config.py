"""
RunConfig — the single in-memory configuration object for an experiment run.

Design
------
``RunConfig`` is the canonical source of truth for every tunable parameter.
It validates all fields at construction time and delegates sub-config creation
to the existing validated dataclasses (``KalmanConfig``, ``ARXTrainConfig``).

Once a run moves out of ``"pending"`` status the configuration is frozen by the
service layer (see ``service.py``).  There is no in-process mutation mechanism.

JSON round-trip
---------------
``RunConfig.to_json()`` / ``RunConfig.from_json()`` are used to populate
``ExperimentConfig.raw_config_json`` so a saved row is fully self-describing
and can reproduce the exact configuration without requiring every column to be
re-read individually.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field

from ..kalman.cycle import KalmanConfig
from ..prediction.arx_adapter import ARXTrainConfig, _DEFAULT_INPUT_COLS

# ── v1 authorization guard ─────────────────────────────────────────────────────
#
# v1 restriction: configuration changes are blocked once a run is no longer in
# "pending" status.  This is enforced by the service layer (service.py).
# There is no role-based auth in v1; the constraint is documented as a
# hard service-layer invariant here for Task #007 onwards.

_IMMUTABLE_AFTER_START_NOTE = (
    "RunConfig is immutable after ExperimentRun.status moves out of 'pending'. "
    "Any mutation attempt via the service layer raises ConfigFrozenError."
)


class ConfigFrozenError(RuntimeError):
    """Raised when an attempt is made to modify a run config after run start."""


# ── Constants ─────────────────────────────────────────────────────────────────

_VALID_PREPROCESS_POLICIES = frozenset({"keep_last", "interpolate", "skip"})


# ── RunConfig dataclass ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class RunConfig:
    """Frozen configuration snapshot for one estimation run.

    All defaults match ADR-003 locked decisions (Task #001).

    The dataclass is frozen so that a ``RunConfig`` object cannot be mutated
    after construction; the service layer creates a new instance when a
    configuration is changed before run start.

    Parameters
    ----------
    name:
        Human-readable label for the run.
    dataset_source:
        CSV path or MySQL table/query description. Stored for provenance.

    Kalman fields (validated via ``KalmanConfig``)
    -----------------------------------------------
    x0, P0, Q, R0, R_min, R_max, alpha

    Chronological split ratios
    --------------------------
    train_ratio, val_ratio, test_ratio  — must be positive, sum to 1.0.

    ARX fields (validated via ``ARXTrainConfig``)
    ---------------------------------------------
    arx_na, arx_nb, arx_nk
    arx_input_cols  — tuple of column names drawn from the ARX field map.

    Preprocessing
    -------------
    preprocessing_policy  — one of "keep_last", "interpolate", "skip".
    """

    # Run metadata
    name: str = "unnamed_run"
    dataset_source: str = ""

    # ── Kalman parameters ──────────────────────────────────────────────────────
    x0: float = 0.0
    P0: float = 1.0
    Q: float = 0.05
    R0: float = 1.0
    R_min: float = 0.05
    R_max: float = 25.0
    alpha: float = 0.95

    # ── Split ratios ───────────────────────────────────────────────────────────
    train_ratio: float = 0.60
    val_ratio: float = 0.20
    test_ratio: float = 0.20

    # ── ARX model order ────────────────────────────────────────────────────────
    arx_na: int = 2
    arx_nb: int = 2
    arx_nk: int = 1
    arx_input_cols: tuple[str, ...] = field(default=_DEFAULT_INPUT_COLS)

    # ── Preprocessing ──────────────────────────────────────────────────────────
    preprocessing_policy: str = "keep_last"

    # ── Validation ────────────────────────────────────────────────────────────

    def __post_init__(self) -> None:
        # Coerce arx_input_cols to an immutable tuple regardless of what the caller
        # passed (list, generator, etc.).  Must be done via object.__setattr__
        # because the dataclass is frozen — direct assignment raises FrozenInstanceError.
        object.__setattr__(self, "arx_input_cols", tuple(self.arx_input_cols))

        # Delegate Kalman validation — reuses KalmanConfig's battle-tested checks.
        KalmanConfig(
            x0=self.x0,
            P0=self.P0,
            Q=self.Q,
            R0=self.R0,
            R_min=self.R_min,
            R_max=self.R_max,
            alpha=self.alpha,
        )

        # Split ratios: each positive, sum == 1.0
        for _name, _val in (
            ("train_ratio", self.train_ratio),
            ("val_ratio", self.val_ratio),
            ("test_ratio", self.test_ratio),
        ):
            if not math.isfinite(_val) or _val <= 0.0:
                raise ValueError(f"{_name} must be a positive finite float, got {_val!r}")
        _total = self.train_ratio + self.val_ratio + self.test_ratio
        if not math.isclose(_total, 1.0, abs_tol=1e-6):
            raise ValueError(
                f"train_ratio + val_ratio + test_ratio must sum to 1.0, "
                f"got {_total!r}"
            )

        # ARX validation — reuses ARXTrainConfig's checks.
        ARXTrainConfig(
            na=self.arx_na,
            nb=self.arx_nb,
            nk=self.arx_nk,
            input_cols=self.arx_input_cols,
        )

        # Preprocessing policy
        if self.preprocessing_policy not in _VALID_PREPROCESS_POLICIES:
            raise ValueError(
                f"preprocessing_policy must be one of {sorted(_VALID_PREPROCESS_POLICIES)}, "
                f"got {self.preprocessing_policy!r}"
            )

    # ── Sub-config extraction ─────────────────────────────────────────────────

    def to_kalman_config(self) -> KalmanConfig:
        """Return the ``KalmanConfig`` corresponding to this run's Kalman parameters."""
        return KalmanConfig(
            x0=self.x0,
            P0=self.P0,
            Q=self.Q,
            R0=self.R0,
            R_min=self.R_min,
            R_max=self.R_max,
            alpha=self.alpha,
        )

    def to_arx_train_config(self) -> ARXTrainConfig:
        """Return the ``ARXTrainConfig`` corresponding to this run's ARX parameters."""
        return ARXTrainConfig(
            na=self.arx_na,
            nb=self.arx_nb,
            nk=self.arx_nk,
            input_cols=self.arx_input_cols,
        )

    # ── JSON serialisation ────────────────────────────────────────────────────

    def to_json(self) -> str:
        """Serialise to a JSON string suitable for ``ExperimentConfig.raw_config_json``."""
        d = asdict(self)
        # tuple fields are not JSON-serialisable directly; convert to list.
        d["arx_input_cols"] = list(d["arx_input_cols"])
        return json.dumps(d, ensure_ascii=False)

    @classmethod
    def from_json(cls, raw: str) -> "RunConfig":
        """Deserialise from ``ExperimentConfig.raw_config_json``.

        Raises ``ValueError`` if the payload is missing required fields or
        contains invalid values.
        """
        try:
            d = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON for RunConfig: {exc}") from exc
        # Re-inflate tuple field.
        if "arx_input_cols" in d:
            d["arx_input_cols"] = tuple(d["arx_input_cols"])
        try:
            return cls(**d)
        except TypeError as exc:
            raise ValueError(f"RunConfig JSON has unexpected fields: {exc}") from exc

    # ── ORM round-trip ────────────────────────────────────────────────────────

    @classmethod
    def from_experiment_config(cls, db_row: object) -> "RunConfig":
        """Reconstruct a ``RunConfig`` from an ``ExperimentConfig`` ORM row.

        Reads the structured columns (not ``raw_config_json``) so the result
        is authoritative even if the JSON snapshot is from an older schema.
        The ARX input_cols fall back to the defaults when the row was created
        before this field existed.
        """
        # arx_input_cols may not be stored directly on the Django model (it lives
        # in raw_config_json).  Try JSON first; fall back to default.
        arx_cols: tuple[str, ...] = _DEFAULT_INPUT_COLS
        raw_json: str = getattr(db_row, "raw_config_json", "{}")
        try:
            parsed = json.loads(raw_json)
            if "arx_input_cols" in parsed:
                arx_cols = tuple(parsed["arx_input_cols"])
        except (json.JSONDecodeError, TypeError):
            pass

        run = getattr(db_row, "run", None)
        name: str = getattr(run, "name", "unnamed_run") if run is not None else "unnamed_run"
        dataset_source: str = (
            getattr(run, "dataset_source", "") or ""
            if run is not None
            else ""
        )

        return cls(
            name=name,
            dataset_source=dataset_source,
            x0=db_row.x0,  # type: ignore[union-attr]
            P0=db_row.P0,  # type: ignore[union-attr]
            Q=db_row.Q,  # type: ignore[union-attr]
            R0=db_row.R0,  # type: ignore[union-attr]
            R_min=db_row.R_min,  # type: ignore[union-attr]
            R_max=db_row.R_max,  # type: ignore[union-attr]
            alpha=db_row.alpha,  # type: ignore[union-attr]
            train_ratio=db_row.train_ratio,  # type: ignore[union-attr]
            val_ratio=db_row.val_ratio,  # type: ignore[union-attr]
            test_ratio=db_row.test_ratio,  # type: ignore[union-attr]
            arx_na=db_row.arx_na,  # type: ignore[union-attr]
            arx_nb=db_row.arx_nb,  # type: ignore[union-attr]
            arx_nk=db_row.arx_nk,  # type: ignore[union-attr]
            arx_input_cols=arx_cols,
            preprocessing_policy=db_row.preprocessing_policy,  # type: ignore[union-attr]
        )
