import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, CheckCircle, Droplets, Gauge, RefreshCw, Sprout, Square, Zap } from "lucide-react";
import {
  getForecast,
  startAmpcScheduler,
  stopAmpcScheduler,
} from "../api/endpoints";
import type { AMPCRecommendation, AMPCSchedulerState, Fao56Audit, ForecastResponse } from "../api/endpoints";
import { Button } from "./ui/button";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export type ChartRow = {
  label: string;
  soilActual: number | null;
  soilForecast: number | null;
  temperature: number | null;
  humidity: number | null;
};

type FaoStressTone = "wet" | "safe" | "stress" | "unknown";

const INTERNAL_REASON_TOKENS = [
  "traceback",
  "stack trace",
  "file \"",
  ".py",
  "valueerror",
  "typeerror",
  "exception",
  "line ",
  "invalid_fao_config",
  "config_error:",
];

function fmt(value: number | null | undefined, digits = 1) {
  const numeric = Number(value);
  if (value === null || value === undefined || !Number.isFinite(numeric)) return "--";
  return numeric.toFixed(digits);
}

function finiteNumber(value: number | null | undefined) {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function fmtMetric(value: number | null | undefined, digits = 2, unit = "") {
  const numeric = finiteNumber(value);
  if (numeric === null) return "--";
  return `${numeric.toFixed(digits)}${unit}`;
}

function timeLabel(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "--:--";
  return date.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" });
}

function describeSafetyStatus(status?: string) {
  const labels: Record<string, string> = {
    safe: "an toàn",
    model_error: "lỗi mô hình",
    stale_sample: "dữ liệu cảm biến quá cũ",
    config_error: "lỗi cấu hình",
    sensor_error: "lỗi cảm biến",
    pump_off_failsafe: "đã tắt bơm theo fail-safe",
    error: "lỗi hệ thống",
  };
  return labels[status ?? ""] ?? status ?? "không rõ trạng thái";
}

function looksInternalReason(reason: string) {
  const normalized = reason.toLowerCase();
  return INTERNAL_REASON_TOKENS.some((token) => normalized.includes(token));
}

export function describeReason(reason?: string) {
  if (!reason) return "không rõ nguyên nhân";

  const normalized = reason.toLowerCase();
  if (normalized.includes("history_too_short")) {
    return "chưa đủ dữ liệu lịch sử cho ARX/AMPC";
  }
  if (normalized.includes("missing_estimation")) {
    return "chưa có kết quả Kalman hợp lệ";
  }
  if (normalized.includes("artifact not found")) {
    return "không tìm thấy artifact mô hình ARX";
  }
  if (normalized.includes("stale")) {
    return "mẫu cảm biến đã quá cũ";
  }
  if (looksInternalReason(reason)) {
    return "lỗi cấu hình hoặc mô hình đã được ghi trong audit backend";
  }
  if (reason.length > 120) {
    return "backend trả về lỗi dài; chi tiết đã được ghi trong audit";
  }
  return reason;
}

export function buildAmpcError(
  recommendation: AMPCRecommendation | null,
  scheduler: AMPCSchedulerState | null
) {
  if (recommendation && recommendation.safety_status !== "safe") {
    const status = describeSafetyStatus(recommendation.safety_status);
    const reason = describeReason(recommendation.reason);
    return `Lỗi AMPC: ${status} - ${reason}`;
  }
  if (scheduler?.last_error) {
    const status = describeSafetyStatus(scheduler.last_status);
    const reason = describeReason(scheduler.last_error);
    return `Lỗi AMPC: ${status} - ${reason}`;
  }
  return "";
}

export function buildForecastChartData(data: ForecastResponse | null): ChartRow[] {
  const rows = (data?.history ?? []).map((item) => ({
    label: timeLabel(item.recorded_at),
    soilActual: item.soil_moisture,
    soilForecast: null,
    temperature: item.temperature,
    humidity: item.humidity,
  }));

  const latest = data?.latest;
  const predictions = data?.recommendation?.predicted_soil_moisture ?? [];
  if (latest && rows.length === 0) {
    rows.push({
      label: "Hiện tại",
      soilActual: latest.soil_moisture,
      soilForecast: null,
      temperature: latest.temperature,
      humidity: latest.humidity,
    });
  }

  const forecastAnchor = latest?.recorded_at ? new Date(latest.recorded_at) : null;
  const stepMilliseconds = Math.max(1, data?.recommendation?.step_seconds ?? 300) * 1000;

  predictions.slice(0, 6).forEach((value, index) => {
    const forecastTime =
      forecastAnchor && !Number.isNaN(forecastAnchor.getTime())
        ? new Date(forecastAnchor.getTime() + stepMilliseconds * (index + 1))
        : null;

    rows.push({
      label: forecastTime ? timeLabel(forecastTime.toISOString()) : `+${index + 1}`,
      soilActual: null,
      soilForecast: value,
      temperature: latest?.temperature ?? null,
      humidity: latest?.humidity ?? null,
    });
  });
  return rows;
}

export function getFaoAudit(recommendation: AMPCRecommendation | null): Fao56Audit | null {
  return recommendation?.state_snapshot?.fao56 ?? null;
}

export function describeFaoStressStatus(fao: Fao56Audit | null | undefined): {
  label: string;
  tone: FaoStressTone;
  detail: string;
} {
  const dr = finiteNumber(fao?.initial_dr);
  const raw = finiteNumber(fao?.raw);

  if (dr === null || raw === null) {
    return {
      label: "Chưa có trạng thái FAO",
      tone: "unknown",
      detail: "Lần chạy này chưa có đủ Dr/RAW để phân loại stress.",
    };
  }
  if (Math.abs(dr) <= 1e-9) {
    return {
      label: "Wet / no-irrigation",
      tone: "wet",
      detail: "Dr = 0 mm, vùng rễ đang ở trạng thái ướt.",
    };
  }
  if (dr <= raw) {
    return {
      label: "Safe zone",
      tone: "safe",
      detail: "Dr <= RAW, cây chưa vào vùng stress nước.",
    };
  }
  return {
    label: "Water stress",
    tone: "stress",
    detail: "Dr > RAW, MPC đang thấy thiếu nước theo FAO-56.",
  };
}

function stressToneClass(tone: FaoStressTone) {
  const classes: Record<FaoStressTone, string> = {
    wet: "border-sky-100 bg-sky-50 text-sky-700",
    safe: "border-green-100 bg-green-50 text-green-700",
    stress: "border-amber-100 bg-amber-50 text-amber-700",
    unknown: "border-slate-100 bg-slate-50 text-slate-600",
  };
  return classes[tone];
}

export function FaoAuditPanel({ recommendation }: { recommendation: AMPCRecommendation | null }) {
  const fao = getFaoAudit(recommendation);
  const stress = describeFaoStressStatus(fao);
  const metrics = [
    { label: "Dr", value: fmtMetric(fao?.initial_dr, 2, " mm") },
    { label: "TAW", value: fmtMetric(fao?.taw, 2, " mm") },
    { label: "RAW", value: fmtMetric(fao?.raw, 2, " mm") },
    { label: "Ks", value: fmtMetric(fao?.ks, 3) },
    { label: "ET0_step", value: fmtMetric(fao?.et0_step, 3, " mm") },
    { label: "ETc_adj", value: fmtMetric(fao?.etc_adj, 3, " mm") },
    { label: "irrigation_depth_mm", value: fmtMetric(fao?.irrigation_depth_mm, 3, " mm") },
  ];

  return (
    <section className="elevated-card rounded-3xl p-5" data-testid="fao-audit-panel">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <Gauge className="w-5 h-5 text-emerald-600" aria-hidden="true" />
            <p className="text-slate-800" style={{ fontSize: "15px", fontWeight: 800 }}>
              FAO-56 audit
            </p>
          </div>
          <p className="mt-1 text-slate-500" style={{ fontSize: "12px" }}>
            Chỉ số vật lý của bộ điều khiển; đồ thị dự báo bên dưới vẫn là % sensor.
          </p>
        </div>
        <span
          className={`rounded-full border px-3 py-1 ${stressToneClass(stress.tone)}`}
          data-testid="fao-stress-status"
          style={{ fontSize: "11px", fontWeight: 800 }}
        >
          {stress.label}
        </span>
      </div>

      <p className="mt-3 text-slate-500" style={{ fontSize: "12px" }}>
        {stress.detail}
      </p>

      <dl className="mt-4 grid grid-cols-2 gap-x-5 gap-y-3 border-t border-slate-100 pt-4 md:grid-cols-4">
        {metrics.map((metric) => (
          <div key={metric.label} className="min-w-0">
            <dt className="truncate text-slate-400" style={{ fontSize: "11px", fontWeight: 700 }}>
              {metric.label}
            </dt>
            <dd className="mt-1 text-slate-900" style={{ fontSize: "18px", fontWeight: 800 }}>
              {metric.value}
            </dd>
          </div>
        ))}
      </dl>

      {!fao && (
        <p className="mt-3 rounded-2xl border border-slate-100 bg-slate-50 px-3 py-2 text-slate-600" style={{ fontSize: "12px" }}>
          Chưa có dữ liệu audit FAO-56 cho lần chạy này.
        </p>
      )}
    </section>
  );
}

export function ForecastPage() {
  const [data, setData] = useState<ForecastResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [ampcRunning, setAmpcRunning] = useState(false);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const response = await getForecast();
      setData(response.data);
      setAmpcRunning(response.data.scheduler?.is_enabled ?? false);
    } catch {
      setError("Không tải được dữ liệu dự báo.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  useEffect(() => {
    if (!ampcRunning) return undefined;

    const timer = window.setInterval(() => {
      load();
    }, 10000);

    return () => window.clearInterval(timer);
  }, [ampcRunning]);

  const stopAmpc = async () => {
    setRunning(true);
    setError("");
    try {
      const response = await stopAmpcScheduler();
      setAmpcRunning(response.data.is_enabled);
      await load();
    } catch {
      setError("Lỗi AMPC: không gọi được backend.");
    } finally {
      setRunning(false);
    }
  };

  const startAmpc = async () => {
    setRunning(true);
    setError("");
    try {
      const response = await startAmpcScheduler();
      setAmpcRunning(response.data.is_enabled);
      await load();
    } catch {
      setError("Lỗi AMPC: không gọi được backend.");
    } finally {
      setRunning(false);
    }
  };

  const chartData = useMemo<ChartRow[]>(() => buildForecastChartData(data), [data]);

  const latest = data?.latest ?? null;
  const recommendation = data?.recommendation ?? null;
  const scheduler = data?.scheduler ?? null;
  const isSafe = recommendation?.safety_status === "safe";
  const ampcError = buildAmpcError(recommendation, scheduler);

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-slate-500" style={{ fontSize: "12px", fontWeight: 700 }}>
            Dự báo AMPC
          </p>
          <p className="text-slate-900" style={{ fontSize: "22px", fontWeight: 800 }}>
            Dự báo độ ẩm đất và lệnh bơm
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button onClick={load} disabled={loading || running} variant="outline" size="sm">
            <RefreshCw className="w-4 h-4 mr-2" />
            Tải lại
          </Button>
          <Button
            onClick={ampcRunning ? stopAmpc : startAmpc}
            disabled={running}
            variant={ampcRunning ? "outline" : "default"}
            size="sm"
          >
            {ampcRunning ? <Square className="w-4 h-4 mr-2" /> : <Zap className="w-4 h-4 mr-2" />}
            {ampcRunning ? "Dừng AMPC" : "Chạy AMPC"}
          </Button>
        </div>
      </div>

      <div
        className={`rounded-2xl border px-4 py-3 ${
          ampcRunning
            ? "border-green-100 bg-green-50 text-green-700"
            : "border-slate-100 bg-slate-50 text-slate-600"
        }`}
        style={{ fontSize: "13px" }}
      >
        {ampcRunning
          ? "AMPC đang chạy ở backend: hệ thống vẫn tính lại mỗi 5 phút kể cả khi đóng hoặc tải lại trang web."
          : "AMPC đang dừng: bấm Chạy AMPC để bật vòng dự báo nền ở backend."}
      </div>

      {error && (
        <div className="rounded-2xl border border-red-100 bg-red-50 px-4 py-3 text-red-700" style={{ fontSize: "13px" }}>
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="elevated-card rounded-3xl p-5">
          <div className="flex items-center justify-between mb-4">
            <Sprout className="w-5 h-5 text-green-600" />
            <span className="text-slate-400" style={{ fontSize: "11px" }}>
              {latest ? timeLabel(latest.recorded_at) : "Chưa có dữ liệu"}
            </span>
          </div>
          <p className="text-slate-500" style={{ fontSize: "12px" }}>Độ ẩm đất hiện tại</p>
          <p className="text-slate-900 mt-1" style={{ fontSize: "30px", fontWeight: 800 }}>
            {fmt(latest?.soil_moisture)}%
          </p>
        </div>

        <div className="elevated-card rounded-3xl p-5">
          <div className="flex items-center justify-between mb-4">
            <Droplets className="w-5 h-5 text-blue-600" />
            {isSafe ? <CheckCircle className="w-5 h-5 text-green-600" /> : <AlertTriangle className="w-5 h-5 text-amber-600" />}
          </div>
          <p className="text-slate-500" style={{ fontSize: "12px" }}>Lệnh bơm đề xuất</p>
          <p className="text-slate-900 mt-1" style={{ fontSize: "30px", fontWeight: 800 }}>
            {fmt(recommendation?.pump_seconds ?? 0, 0)}s
          </p>
          <p className="text-slate-400 mt-1" style={{ fontSize: "11px" }}>
            {recommendation ? describeSafetyStatus(recommendation.safety_status) : "chưa chạy AMPC"}
          </p>
        </div>

        <div className="elevated-card rounded-3xl p-5">
          <p className="text-slate-500" style={{ fontSize: "12px" }}>Bias AMPC</p>
          <p className="text-slate-900 mt-1" style={{ fontSize: "30px", fontWeight: 800 }}>
            {fmt(recommendation?.bias_correction ?? 0)}%
          </p>
          <p className="text-slate-400 mt-1" style={{ fontSize: "11px" }}>
            số mẫu sai lệch: {recommendation?.bias_window_count ?? 0}
          </p>
        </div>
      </div>

      <FaoAuditPanel recommendation={recommendation} />

      <div className="elevated-card rounded-3xl p-5">
        <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
          <div>
            <p className="text-slate-800" style={{ fontSize: "15px", fontWeight: 800 }}>
              Dự báo độ ẩm đất
            </p>
            <p className="text-slate-500" style={{ fontSize: "12px" }}>
              Đường xanh lá là dữ liệu sensor, đường xanh dương là dự báo AMPC.
            </p>
            {ampcError && (
              <p className="mt-2 rounded-xl border border-red-100 bg-red-50 px-3 py-2 text-red-700" style={{ fontSize: "12px", fontWeight: 700 }}>
                {ampcError}
              </p>
            )}
          </div>
          <span className="rounded-full bg-slate-50 px-3 py-1 text-slate-600 border border-slate-100" style={{ fontSize: "11px", fontWeight: 700 }}>
            chi phí {fmt(recommendation?.objective_cost, 2)}
          </span>
        </div>

        <ResponsiveContainer width="100%" height={320}>
          <LineChart data={chartData} margin={{ top: 12, right: 18, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#eef2f7" vertical={false} />
            <XAxis dataKey="label" tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} domain={[0, 100]} width={34} />
            <Tooltip />
            {recommendation?.target_band?.low !== undefined && (
              <ReferenceLine y={recommendation.target_band.low} stroke="#f59e0b" strokeDasharray="4 4" />
            )}
            {recommendation?.target_band?.high !== undefined && (
              <ReferenceLine y={recommendation.target_band.high} stroke="#f59e0b" strokeDasharray="4 4" />
            )}
            <Line type="monotone" dataKey="soilActual" stroke="#16a34a" strokeWidth={3} dot={{ r: 3 }} connectNulls={false} />
            <Line type="monotone" dataKey="soilForecast" stroke="#2563eb" strokeWidth={3} strokeDasharray="5 5" dot={{ r: 3 }} connectNulls={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
