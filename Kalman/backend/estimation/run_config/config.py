"""
RunConfig là object cấu hình trong bộ nhớ cho một experiment run.

Thiết kế
--------
``RunConfig`` là nguồn sự thật chính cho mọi tham số Kalman có thể tune. Nó
validate tất cả field khi khởi tạo và giao việc tạo sub-config cho
``KalmanConfig``.

Khi run không còn trạng thái ``"pending"``, cấu hình bị khóa bởi tầng service
(xem ``service.py``). Không có cơ chế mutate trực tiếp trong process.

Vòng đời JSON
-------------
``RunConfig.to_json()`` / ``RunConfig.from_json()`` được dùng để ghi
``ExperimentConfig.raw_config_json``. Nhờ vậy một dòng đã lưu tự mô tả đầy đủ
và có thể tái tạo đúng cấu hình mà không cần đọc lại từng cột riêng lẻ.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from ..kalman.cycle import KalmanConfig

# ── Chốt quyền chỉnh config ở v1 ──────────────────────────────────────────────
#
# Ràng buộc v1: không cho đổi cấu hình khi run không còn trạng thái "pending".
# Điều này được enforce ở tầng service (service.py). v1 chưa có phân quyền theo
# role; ràng buộc này được ghi lại như một invariant cứng của service từ
# Task #007 trở đi.

_IMMUTABLE_AFTER_START_NOTE = (
    "RunConfig is immutable after ExperimentRun.status moves out of 'pending'. "
    "Any mutation attempt via the service layer raises ConfigFrozenError."
)


class ConfigFrozenError(RuntimeError):
    """Raise khi cố sửa config sau khi run đã bắt đầu."""


# ── Dataclass RunConfig ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class RunConfig:
    """Snapshot cấu hình dạng frozen cho một lần chạy ước lượng.

    Tất cả giá trị mặc định khớp với runtime live đã chốt ở ADR-004.

    Dataclass này frozen để object ``RunConfig`` không bị mutate sau khi tạo.
    Nếu cần đổi cấu hình trước khi run bắt đầu, tầng service sẽ tạo instance mới.

    Parameters
    ----------
    name:
        Tên dễ đọc cho run.
    dataset_source:
        Mô tả device, deployment, hoặc live source. Dùng để truy vết nguồn dữ liệu.

    Các field Kalman, validate qua ``KalmanConfig``
    ------------------------------------------------
    x0, P0, Q, R0, R_min, R_max, alpha

    Live preprocessing always skips invalid measurements; it is not configurable.
    """

    # Metadata của run
    name: str = "unnamed_run"
    dataset_source: str = ""

    # ── Tham số Kalman ────────────────────────────────────────────────────────
    x0: float = 0.0
    P0: float = 1.0
    Q: float = 0.05
    R0: float = 1.0
    R_min: float = 0.05
    R_max: float = 25.0
    alpha: float = 0.95

    # ── Validate ──────────────────────────────────────────────────────────────

    def __post_init__(self) -> None:
        # Giao validate Kalman cho KalmanConfig để tái sử dụng các check đã có.
        KalmanConfig(
            x0=self.x0,
            P0=self.P0,
            Q=self.Q,
            R0=self.R0,
            R_min=self.R_min,
            R_max=self.R_max,
            alpha=self.alpha,
        )

    # ── Trích sub-config ─────────────────────────────────────────────────────

    def to_kalman_config(self) -> KalmanConfig:
        """Trả về ``KalmanConfig`` tương ứng với tham số Kalman của run này."""
        return KalmanConfig(
            x0=self.x0,
            P0=self.P0,
            Q=self.Q,
            R0=self.R0,
            R_min=self.R_min,
            R_max=self.R_max,
            alpha=self.alpha,
        )

    # ── Serialize JSON ───────────────────────────────────────────────────────

    def to_json(self) -> str:
        """Serialize thành chuỗi JSON để ghi vào ``ExperimentConfig.raw_config_json``."""
        d = asdict(self)
        return json.dumps(d, ensure_ascii=False)

    @classmethod
    def from_json(cls, raw: str) -> "RunConfig":
        """Deserialize từ ``ExperimentConfig.raw_config_json``.

        Raise ``ValueError`` nếu payload thiếu field bắt buộc hoặc có giá trị
        không hợp lệ.
        """
        try:
            d = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON for RunConfig: {exc}") from exc
        if not isinstance(d, dict):
            raise ValueError("RunConfig JSON must be an object")
        # Drop pre-ADR-004 offline/ARX-train keys so old snapshots can still be
        # loaded after the live-only cleanup.
        for key in (
            "train_ratio",
            "val_ratio",
            "test_ratio",
            "arx_na",
            "arx_nb",
            "arx_nk",
            "arx_input_cols",
            "preprocessing_policy",
        ):
            d.pop(key, None)
        try:
            return cls(**d)
        except TypeError as exc:
            raise ValueError(f"RunConfig JSON has unexpected fields: {exc}") from exc

    # ── Vòng đời ORM ─────────────────────────────────────────────────────────

    @classmethod
    def from_experiment_config(cls, db_row: object) -> "RunConfig":
        """Dựng lại ``RunConfig`` từ một dòng ORM ``ExperimentConfig``.

        Đọc các cột có cấu trúc thay vì chỉ đọc ``raw_config_json``, để kết quả
        vẫn là nguồn đáng tin kể cả khi snapshot JSON thuộc schema cũ. Nếu dòng
        được tạo trước khi có field ARX input_cols thì fallback về mặc định.
        """
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
        )
