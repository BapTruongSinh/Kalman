"""
Chu kỳ ước lượng Adaptive Kalman cho biến vô hướng Soil_Moisture.

Thuật toán dùng R thích nghi theo innovation và có giới hạn trên/dưới
(Q được giữ cố định trong từng lần chạy). Quyết định này được chốt ở
Task #001 (ADR-003).

Bước dự đoán (time update)
--------------------------
    x_prior  = y_hat_k   if ARX prediction is available and status == "ok"
               else x_post_prev   (last posterior, carry-forward)
    P_prior  = P_post_prev + Q

Bước cập nhật đo lường (khi có z_k và preprocess_status != "skipped")
----------------------------------------------------------------------
    e_k      = z_k - x_prior
    R_k      = clip(alpha * R_{k-1} + (1 - alpha) * e_k^2, R_min, R_max)
    K_k      = P_prior / (P_prior + R_k)
    x_post   = x_prior + K_k * e_k
    P_post   = (1 - K_k) * P_prior

Khi không có đo lường
---------------------
    x_post   = x_prior   (carry prior forward)
    P_post   = P_prior   (covariance grows with Q in the next prediction step)
    R        unchanged

Ràng buộc thiết kế
------------------
- ``step()`` **không bao giờ raise**; mọi lỗi được trả về qua
  ``cycle_status="error"``.
- Trạng thái có thể thay đổi được cô lập trong ``KalmanState``; config là
  frozen dataclass.
- Prediction adapter là phụ thuộc tùy chọn; nếu thiếu thì hệ thống fallback
  về posterior trước đó.
"""

from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from ..ingestion import ProcessedRecord
from ..prediction import PredictionAdapter, PredictionInput, PredictionResult

logger = logging.getLogger(__name__)

_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def _safe_getattr(obj: object, name: str, default: object) -> object:
    """Trả về ``getattr(obj, name)`` hoặc *default*; **không bao giờ raise**.

    Khác với ``getattr(obj, name, default)`` thông thường, hàm này bắt cả lỗi
    do descriptor/property gây ra, để nhánh xử lý lỗi của Kalman không bị raise
    ngược lại khi gặp input xấu.
    """
    try:
        return getattr(obj, name, default)
    except Exception:  # noqa: BLE001
        return default


def _safe_finite_float_or_none(value: object) -> float | None:
    """Ép *value* về ``float`` hữu hạn, hoặc trả ``None``; **không bao giờ raise**.

    Xử lý cả các subclass của ``float`` có thể override ``__float__`` và tự
    raise lỗi. Cả bước ép kiểu ``float()`` và kiểm tra ``isfinite`` được bọc
    trong một ``try/except`` để không lỗi nào lọt ra ngoài.
    """
    try:
        f = float(value)  # type: ignore[arg-type]
        return f if math.isfinite(f) else None
    except Exception:  # noqa: BLE001
        return None


# ── Cấu hình ─────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class KalmanConfig:
    """Các siêu tham số cho chu kỳ ước lượng Adaptive Kalman.

    Giá trị mặc định khớp với quyết định đã chốt trong ADR-003 (Task #001).

    Parameters
    ----------
    x0:
        Ước lượng trạng thái ban đầu. Thường đặt bằng giá trị
        ``Soil_Moisture`` đầu tiên trước khi chạy.
    P0:
        Hiệp phương sai lỗi ban đầu (> 0).
    Q:
        Hiệp phương sai nhiễu quá trình (>= 0); giữ cố định trong một run và
        thường tune trên tập validation. Giá trị 0 nghĩa là giả định động học
        dự đoán hoàn hảo, không có nhiễu quá trình.
    R0:
        Hiệp phương sai nhiễu đo lường ban đầu (> 0); phải nằm trong
        [R_min, R_max].
    R_min:
        Cận dưới cho R thích nghi (phải lớn hơn 0).
    R_max:
        Cận trên cho R thích nghi. Phải thỏa R_min < R_max.
    alpha:
        Hệ số làm mượt EMA cho R thích nghi. Phải nằm trong [0, 1]; alpha càng
        cao thì R càng ì, thay đổi chậm hơn.
    """

    x0: float = 0.0
    P0: float = 1.0
    Q: float = 0.05
    R0: float = 1.0
    R_min: float = 0.05
    R_max: float = 15.0
    alpha: float = 0.95

    def __post_init__(self) -> None:
        # Tất cả số thực phải hữu hạn trước khi kiểm tra cận, để NaN/Inf không
        # lọt qua âm thầm. Trong Python, so sánh với NaN thường trả False, làm
        # các điều kiện biên có thể bị bỏ qua và NaN lan vào bộ lọc.
        for _field, _val in (
            ("x0", self.x0),
            ("P0", self.P0),
            ("Q", self.Q),
            ("R0", self.R0),
            ("R_min", self.R_min),
            ("R_max", self.R_max),
            ("alpha", self.alpha),
        ):
            if not math.isfinite(_val):
                raise ValueError(f"{_field} must be finite, got {_val!r}")
        if self.P0 <= 0.0:
            raise ValueError(f"P0 must be > 0, got {self.P0!r}")
        if self.Q < 0.0:
            raise ValueError(f"Q must be >= 0, got {self.Q!r}")
        if self.R0 <= 0.0:
            raise ValueError(f"R0 must be > 0, got {self.R0!r}")
        if not (0.0 < self.R_min < self.R_max):
            raise ValueError(
                f"Must satisfy 0 < R_min < R_max; "
                f"got R_min={self.R_min!r}, R_max={self.R_max!r}"
            )
        if not (self.R_min <= self.R0 <= self.R_max):
            raise ValueError(
                f"R0 must be in [R_min, R_max]; "
                f"got R0={self.R0!r}, R_min={self.R_min!r}, R_max={self.R_max!r}"
            )
        if not (0.0 <= self.alpha <= 1.0):
            raise ValueError(f"alpha must be in [0, 1], got {self.alpha!r}")


# ── Trạng thái bộ lọc có thể thay đổi ─────────────────────────────────────────


@dataclass
class KalmanState:
    """Trạng thái được giữ giữa các lần gọi ``step()`` liên tiếp.

    Attributes
    ----------
    x_post:
        Ước lượng posterior hiện tại, tức Soil_Moisture sau lọc.
    P_post:
        Hiệp phương sai lỗi posterior hiện tại.
    R:
        Hiệp phương sai nhiễu đo lường thích nghi hiện tại.
    step:
        Số bước thời gian đã xử lý đến hiện tại, đếm từ 0.
    """

    x_post: float
    P_post: float
    R: float
    step: int = 0

    @classmethod
    def from_config(cls, config: KalmanConfig) -> "KalmanState":
        """Khởi tạo trạng thái mới từ ``KalmanConfig``."""
        return cls(x_post=config.x0, P_post=config.P0, R=config.R0)


# ── Kết quả của từng chu kỳ ───────────────────────────────────────────────────


@dataclass(frozen=True)
class CycleResult:
    """Kết quả đầu ra cho một bước thời gian đã xử lý.

    Chứa các giá trị Kalman cần để ghi vào model Django ``PipelineCycle``
    (Task #002). Tầng lưu trữ (Task #007) chịu trách nhiệm map các field này
    sang tên cột trong DB và thêm metadata cấp run như ``slice_type``,
    ``source_type``, ``created_at``, các tiền tố ``kf_``...

    Attributes
    ----------
    timestamp:
        Timestamp gốc từ dữ liệu đầu vào.
    cycle_index:
        Chỉ số tuần tự trong run, bắt đầu từ 0.
    raw_soil_moisture:
        Giá trị đo thô đọc từ dữ liệu, trước tiền xử lý.
    preprocess_status:
        Kết quả tiền xử lý live-only: ``"valid"`` hoặc ``"skipped"``.
    arx_predicted:
        Dự đoán Soil_Moisture bước kế tiếp từ ARX; ``None`` nếu không có.
    x_prior:
        Ước lượng trạng thái prior ``x^-_k`` sau bước dự đoán.
    P_prior:
        Hiệp phương sai lỗi prior ``P^-_k`` sau bước dự đoán.
    innovation:
        Sai lệch đo lường ``e_k = z_k - x_prior``; ``None`` khi không cập nhật.
    R:
        Nhiễu đo lường thích nghi ``R_k`` tại bước này.
    K:
        Hệ số Kalman gain ``K_k``; ``None`` khi không có cập nhật đo lường.
    x_posterior:
        Ước lượng trạng thái posterior ``x_k`` sau lọc.
    P_posterior:
        Hiệp phương sai lỗi posterior ``P_k``.
    cycle_status:
        ``"ok"``: cập nhật bình thường có đo lường.
        ``"skipped_no_measurement"``: thiếu đo lường, giữ prior làm posterior.
        ``"error"``: có lỗi bất ngờ, trạng thái không đổi.
    adaptive_status:
        ``"R_updated"``: R thích nghi được tính ở bước này.
        ``"R_skipped"``: không có đo lường, R giữ nguyên.
        ``"skipped"``: bỏ qua bước do nhánh lỗi.
    latency_ms:
        Thời gian xử lý bước này tính bằng mili giây.
    error_message:
        Mô tả lỗi dạng dễ đọc khi ``cycle_status == "error"``.
    """

    # Định danh
    timestamp: datetime
    cycle_index: int

    # Dữ liệu thô / tiền xử lý
    raw_soil_moisture: float | None
    preprocess_status: str

    # Đầu ra của prediction adapter
    arx_predicted: float | None

    # Giá trị nội bộ của Kalman
    x_prior: float
    P_prior: float
    innovation: float | None
    R: float
    K: float | None
    x_posterior: float
    P_posterior: float

    # Chẩn đoán
    cycle_status: str
    adaptive_status: str
    latency_ms: float | None = None
    error_message: str | None = None


# ── Bộ ước lượng ──────────────────────────────────────────────────────────────


class AdaptiveKalmanCycle:
    """Bộ ước lượng Adaptive Kalman vô hướng cho Soil_Moisture.

    Một instance tương ứng với một lần chạy ước lượng. Gọi :meth:`step` cho
    từng ``ProcessedRecord`` đầu vào.

    Example
    -------
    ::

        config = KalmanConfig(x0=first_sm, Q=0.05)
        estimator = AdaptiveKalmanCycle(config, adapter=arx_adapter)

        for i, record in enumerate(test_records):
            result = estimator.step(record, cycle_index=i)
            print(result.x_posterior, result.R, result.cycle_status)

    Parameters
    ----------
    config:
        Bộ siêu tham số dạng frozen.
    adapter:
        Prediction adapter tùy chọn. Nếu có và ``predict()`` trả ``"ok"``, giá
        trị dự đoán được dùng làm prior mean. Nếu không có hoặc dự đoán lỗi,
        hệ thống dùng posterior trước đó.
    """

    def __init__(
        self,
        config: KalmanConfig,
        adapter: PredictionAdapter | None = None,
    ) -> None:
        self._config = config
        self._adapter = adapter
        self._state: KalmanState = KalmanState.from_config(config)
        # Lịch sử nhân quả: chỉ gồm các record đã xử lý, truyền vào adapter.predict().
        self._history: list[ProcessedRecord] = []

    # ── Truy cập public dạng chỉ đọc ──────────────────────────────────────────

    @property
    def state(self) -> KalmanState:
        """Trạng thái hiện tại của bộ lọc, trả về reference chỉ đọc theo quy ước."""
        return self._state

    @property
    def config(self) -> KalmanConfig:
        """Cấu hình frozen."""
        return self._config

    @property
    def history(self) -> list[ProcessedRecord]:
        """Tất cả record đã xử lý theo thứ tự thời gian, trả về bản sao."""
        return list(self._history)

    # ── Một bước xử lý ────────────────────────────────────────────────────────

    def step(
        self,
        record: ProcessedRecord,
        *,
        cycle_index: int,
    ) -> CycleResult:
        """Xử lý một bước thời gian.

        **Không bao giờ raise**; mọi lỗi được trả qua ``cycle_status="error"``
        để caller luôn thu được kết quả và có thể chạy tiếp.

        Lịch sử nội bộ và bộ đếm step vẫn được cập nhật dù bước đó thành công
        hay lỗi.

        Parameters
        ----------
        record:
            Record đã tiền xử lý cho bước thời gian này.
        cycle_index:
            Chỉ số tuần tự do caller truyền vào, bắt đầu từ 0 trong run.

        Returns
        -------
        CycleResult
            Luôn là một object kết quả hợp lệ dạng frozen.
        """
        t0 = time.perf_counter()
        result: CycleResult
        try:
            result = self._step_impl(record, cycle_index=cycle_index, t0=t0)
        except Exception as exc:  # noqa: BLE001
            logger.exception("KalmanCycle step %d raised unexpectedly", cycle_index)
            elapsed = (time.perf_counter() - t0) * 1000.0
            # _safe_getattr bọc getattr trong try/except, nên lỗi từ
            # descriptor/property không thể thoát ra ngoài nhánh xử lý lỗi.
            _raw = _safe_getattr(record, "raw", None)
            _ts_raw = _safe_getattr(_raw, "timestamp", _EPOCH)
            _ts: datetime = _ts_raw if isinstance(_ts_raw, datetime) else _EPOCH
            _sm_raw = _safe_getattr(_raw, "soil_moisture", None)
            _raw_sm: float | None = _safe_finite_float_or_none(_sm_raw)
            _ps_raw = _safe_getattr(record, "preprocess_status", "invalid")
            _pre_status: str = _ps_raw if isinstance(_ps_raw, str) else "invalid"
            # Không mutate state ở nhánh lỗi; giữ lại trạng thái tốt gần nhất.
            result = CycleResult(
                timestamp=_ts,
                cycle_index=cycle_index,
                raw_soil_moisture=_raw_sm,
                preprocess_status=_pre_status,
                arx_predicted=None,
                x_prior=self._state.x_post,
                P_prior=self._state.P_post,
                innovation=None,
                R=self._state.R,
                K=None,
                x_posterior=self._state.x_post,
                P_posterior=self._state.P_post,
                cycle_status="error",
                adaptive_status="skipped",
                latency_ms=elapsed,
                error_message=str(exc),
            )

        # Luôn tăng history và step counter bất kể kết quả.
        # Bọc append để input không đúng kiểu cũng không làm raise tiếp.
        if record is not None:
            try:
                self._history.append(record)
            except Exception:  # noqa: BLE001
                pass
        self._state.step += 1
        return result

    # ── Triển khai nội bộ ─────────────────────────────────────────────────────

    def _step_impl(
        self,
        record: ProcessedRecord,
        *,
        cycle_index: int,
        t0: float,
    ) -> CycleResult:
        """Logic ước lượng chính, được gọi bên trong try/except của :meth:`step`."""
        cfg = self._config
        state = self._state

        # ── 1. Hỏi prediction adapter để dự báo bước kế tiếp ─────────────────
        # Chỉ truyền phần đuôi history mà adapter thật sự cần, để replay giữ
        # độ phức tạp O(n) thay vì O(n²) trên chuỗi dài.
        arx_result: PredictionResult | None = None
        if self._adapter is not None:
            min_hist = getattr(self._adapter, "min_history_len", 0)
            if len(self._history) >= min_hist:
                window = (
                    self._history[-min_hist:] if min_hist > 0 else []
                )
                arx_result = self._adapter.predict(
                    PredictionInput(history=window)
                )

        arx_predicted: float | None = (
            arx_result.value
            if (arx_result is not None and arx_result.status == "ok")
            else None
        )

        # ── 2. Time update (bước dự đoán) ────────────────────────────────────
        # Prior mean: dùng dự đoán ARX nếu có, nếu không thì giữ posterior trước.
        x_prior: float = (
            arx_predicted if arx_predicted is not None else state.x_post
        )
        P_prior: float = state.P_post + cfg.Q

        # ── 3. Kiểm tra có đo lường hay không ────────────────────────────────
        z: float | None = record.soil_moisture
        preprocess_status: str = record.preprocess_status

        # "skipped" nghĩa là đo lường đã bị loại bỏ ở bước tiền xử lý; trong
        # Kalman xem như không có đo lường.
        measurement_ok: bool = (
            z is not None and preprocess_status != "skipped"
        )

        if not measurement_ok:
            # Không có cập nhật đo lường, giữ prior làm posterior.
            elapsed = (time.perf_counter() - t0) * 1000.0
            # Mutate state: prior trở thành posterior mới.
            state.x_post = x_prior
            state.P_post = P_prior
            # R giữ nguyên.
            return CycleResult(
                timestamp=record.raw.timestamp,
                cycle_index=cycle_index,
                raw_soil_moisture=record.raw.soil_moisture,
                preprocess_status=preprocess_status,
                arx_predicted=arx_predicted,
                x_prior=x_prior,
                P_prior=P_prior,
                innovation=None,
                R=state.R,
                K=None,
                x_posterior=x_prior,
                P_posterior=P_prior,
                cycle_status="skipped_no_measurement",
                adaptive_status="R_skipped",
                latency_ms=elapsed,
            )

        # ── 4. Cập nhật đo lường ─────────────────────────────────────────────
        assert z is not None  # đã xác nhận ở trên

        # Innovation, tức sai lệch giữa đo lường và prior.
        e: float = z - x_prior

        # R thích nghi: EMA có chặn biên của bình phương innovation.
        # R tăng khi innovation lớn, giảm khi innovation nhỏ.
        R_raw: float = cfg.alpha * state.R + (1.0 - cfg.alpha) * e * e
        R_new: float = float(max(cfg.R_min, min(cfg.R_max, R_raw)))

        # Kalman gain dạng vô hướng cho state 1 chiều.
        K: float = P_prior / (P_prior + R_new)

        # Posterior sau khi kết hợp prior với đo lường.
        x_post: float = x_prior + K * e
        P_post: float = (1.0 - K) * P_prior

        elapsed = (time.perf_counter() - t0) * 1000.0

        result = CycleResult(
            timestamp=record.raw.timestamp,
            cycle_index=cycle_index,
            raw_soil_moisture=record.raw.soil_moisture,
            preprocess_status=preprocess_status,
            arx_predicted=arx_predicted,
            x_prior=x_prior,
            P_prior=P_prior,
            innovation=e,
            R=R_new,
            K=K,
            x_posterior=x_post,
            P_posterior=P_post,
            cycle_status="ok",
            adaptive_status="R_updated",
            latency_ms=elapsed,
        )

        # Mutate state sau cùng, sau khi CycleResult đã được tạo hoàn chỉnh.
        state.x_post = x_post
        state.P_post = P_post
        state.R = R_new

        return result
