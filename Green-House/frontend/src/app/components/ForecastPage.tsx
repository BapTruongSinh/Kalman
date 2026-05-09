import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, CheckCircle, Droplets, RefreshCw, Sprout, Zap } from "lucide-react";
import {
  ForecastResponse,
  getForecast,
  runAutoRecommendation,
} from "../api/endpoints";
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

export function ForecastPage() {
  const [data, setData] = useState<ForecastResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const response = await getForecast();
      setData(response.data);
    } catch {
      setError("Khong tai duoc du bao.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const run = async () => {
    setRunning(true);
    setError("");
    try {
      await runAutoRecommendation();
      await load();
    } catch {
      setError("Chay AMPC that bai.");
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
        label: "Hien tai",
        soilActual: latest.soil_moisture,
        soilForecast: null,
        temperature: latest.temperature,
        humidity: latest.humidity,
      });
    }

    predictions.slice(0, 6).forEach((value, index) => {
      rows.push({
        label: `+${index + 1}`,
        soilActual: null,
        soilForecast: value,
        temperature: latest?.temperature ?? null,
        humidity: latest?.humidity ?? null,
      });
    });
    return rows;
  }, [data]);

  const latest = data?.latest ?? null;
  const estimation = data?.estimation ?? null;
  const recommendation = data?.recommendation ?? null;
  const isSafe = recommendation?.safety_status === "safe";

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-slate-500" style={{ fontSize: "12px", fontWeight: 700 }}>
            AMPC forecast
          </p>
          <p className="text-slate-900" style={{ fontSize: "22px", fontWeight: 800 }}>
            Du bao do am dat va lenh bom
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button onClick={load} disabled={loading} variant="outline" size="sm">
            <RefreshCw className="w-4 h-4 mr-2" />
            Tai lai
          </Button>
          <Button onClick={run} disabled={running} size="sm">
            <Zap className="w-4 h-4 mr-2" />
            Chay AMPC
          </Button>
        </div>
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
              {latest ? timeLabel(latest.recorded_at) : "No data"}
            </span>
          </div>
          <p className="text-slate-500" style={{ fontSize: "12px" }}>Do am dat hien tai</p>
          <p className="text-slate-900 mt-1" style={{ fontSize: "30px", fontWeight: 800 }}>
            {fmt(estimation?.kf_x_posterior ?? latest?.soil_moisture)}%
          </p>
        </div>

        <div className="elevated-card rounded-3xl p-5">
          <div className="flex items-center justify-between mb-4">
            <Droplets className="w-5 h-5 text-blue-600" />
            {isSafe ? <CheckCircle className="w-5 h-5 text-green-600" /> : <AlertTriangle className="w-5 h-5 text-amber-600" />}
          </div>
          <p className="text-slate-500" style={{ fontSize: "12px" }}>Lenh bom de xuat</p>
          <p className="text-slate-900 mt-1" style={{ fontSize: "30px", fontWeight: 800 }}>
            {fmt(recommendation?.pump_seconds, 0)}s
          </p>
          <p className="text-slate-400 mt-1" style={{ fontSize: "11px" }}>
            {recommendation?.safety_status ?? "chua co recommendation"}
          </p>
        </div>

        <div className="elevated-card rounded-3xl p-5">
          <p className="text-slate-500" style={{ fontSize: "12px" }}>Bias AMPC</p>
          <p className="text-slate-900 mt-1" style={{ fontSize: "30px", fontWeight: 800 }}>
            {fmt(recommendation?.bias_correction)}%
          </p>
          <p className="text-slate-400 mt-1" style={{ fontSize: "11px" }}>
            residual window: {recommendation?.bias_window_count ?? 0}
          </p>
        </div>
      </div>

      <div className="elevated-card rounded-3xl p-5">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
          <div>
            <p className="text-slate-800" style={{ fontSize: "15px", fontWeight: 800 }}>
              Soil moisture horizon
            </p>
            <p className="text-slate-500" style={{ fontSize: "12px" }}>
              Duong xanh la du lieu sensor, duong xanh duong la AMPC forecast.
            </p>
          </div>
          <span className="rounded-full bg-slate-50 px-3 py-1 text-slate-600 border border-slate-100" style={{ fontSize: "11px", fontWeight: 700 }}>
            cost {fmt(recommendation?.objective_cost, 2)}
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
