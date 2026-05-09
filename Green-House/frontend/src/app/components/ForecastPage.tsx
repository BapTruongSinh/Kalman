import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, CheckCircle, Droplets, RefreshCw, Sprout, Square, Zap } from "lucide-react";
import {
  getForecast,
  startAmpcScheduler,
  stopAmpcScheduler,
} from "../api/endpoints";
import type { AMPCRecommendation, AMPCSchedulerState, ForecastResponse } from "../api/endpoints";
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

type ChartRow = {
  label: string;
  soilActual: number | null;
  soilForecast: number | null;
  temperature: number | null;
  humidity: number | null;
};

function fmt(value: number | null | undefined, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "--";
  return Number(value).toFixed(digits);
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

function describeReason(reason?: string) {
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
  return reason;
}

function buildAmpcError(
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

  const chartData = useMemo<ChartRow[]>(() => {
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
  }, [data]);

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
