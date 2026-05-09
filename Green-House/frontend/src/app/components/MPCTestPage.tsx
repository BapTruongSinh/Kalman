import { useEffect, useMemo, useState } from "react";
import { GitCompare, RefreshCw, Target, Waves } from "lucide-react";
import {
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceArea,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { getMPCTestSeries, MPCTestPoint } from "../api/endpoints";
import { Button } from "./ui/button";

type ChartPoint = {
  time: string;
  actual: number | null;
  mpc: number | null;
  ruleBased: number | null;
  mpcPump: number | null;
  rulePump: number | null;
};

function fmt(value: number | null | undefined, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "--";
  return Number(value).toFixed(digits);
}

function timeLabel(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "--:--";
  return date.toLocaleTimeString("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function inBandRate(values: Array<number | null>, low: number, high: number) {
  const valid = values.filter((value): value is number => Number.isFinite(value));
  if (!valid.length) return null;
  const inside = valid.filter((value) => value >= low && value <= high).length;
  return (inside / valid.length) * 100;
}

function switching(values: Array<number | null>) {
  const valid = values.filter((value): value is number => Number.isFinite(value));
  if (valid.length < 2) return null;
  return valid.slice(1).reduce((sum, value, index) => sum + Math.abs(value - valid[index]), 0);
}

function rangeDomain(points: ChartPoint[], low: number, high: number): [number, number] {
  const values = points.flatMap((point) =>
    [point.actual, point.mpc, point.ruleBased].filter((value): value is number => Number.isFinite(value))
  );
  if (!values.length) return [0, 100];
  const min = Math.min(...values, low);
  const max = Math.max(...values, high);
  const padding = Math.max(2, (max - min) * 0.16);
  return [Math.max(0, Math.floor(min - padding)), Math.min(100, Math.ceil(max + padding))];
}

export function MPCTestPage() {
  const [points, setPoints] = useState<MPCTestPoint[]>([]);
  const [sourceTable, setSourceTable] = useState("ampc_recommendations");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const response = await getMPCTestSeries();
      setPoints(response.data.points);
      setSourceTable(response.data.source_table);
      if (response.data.points.length === 0) {
        setError("Chưa có dữ liệu test MPC trong database.");
      }
    } catch {
      setError("Không tải được dữ liệu đánh giá MPC.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const chartData = useMemo<ChartPoint[]>(
    () =>
      points.map((point) => ({
        time: timeLabel(point.timestamp),
        actual: point.actual_soil_moisture,
        mpc: point.mpc_soil_moisture,
        ruleBased: point.rule_based_soil_moisture,
        mpcPump: point.mpc_pump_seconds,
        rulePump: point.rule_based_pump_seconds,
      })),
    [points]
  );

  const targetLow = points[0]?.target_low ?? 55;
  const targetHigh = points[0]?.target_high ?? 65;
  const yDomain = rangeDomain(chartData, targetLow, targetHigh);
  const mpcInBand = inBandRate(chartData.map((point) => point.mpc), targetLow, targetHigh);
  const ruleInBand = inBandRate(chartData.map((point) => point.ruleBased), targetLow, targetHigh);
  const mpcSwitching = switching(chartData.map((point) => point.mpcPump));
  const ruleSwitching = switching(chartData.map((point) => point.rulePump));

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-slate-500" style={{ fontSize: "12px", fontWeight: 700 }}>
            MPC evaluation
          </p>
          <p className="text-slate-900" style={{ fontSize: "22px", fontWeight: 800 }}>
            Đánh giá MPC
          </p>
          <p className="text-slate-500 mt-1" style={{ fontSize: "13px" }}>
            Kiểm tra khả năng giữ độ ẩm trong vùng mục tiêu và so sánh với rule-based.
          </p>
        </div>
        <Button onClick={load} disabled={loading} variant="outline" size="sm">
          <RefreshCw className="w-4 h-4 mr-2" />
          Tải lại
        </Button>
      </div>

      {error && (
        <div className="rounded-2xl border border-amber-100 bg-amber-50 px-4 py-3 text-amber-700" style={{ fontSize: "13px" }}>
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="elevated-card rounded-3xl p-5">
          <Target className="w-5 h-5 text-green-600 mb-4" />
          <p className="text-slate-500" style={{ fontSize: "12px" }}>Vùng mục tiêu</p>
          <p className="text-slate-900 mt-1" style={{ fontSize: "28px", fontWeight: 800 }}>
            {targetLow}-{targetHigh}%
          </p>
          <p className="text-slate-400 mt-1" style={{ fontSize: "11px" }}>
            soil moisture band
          </p>
        </div>

        <div className="elevated-card rounded-3xl p-5">
          <Waves className="w-5 h-5 text-blue-600 mb-4" />
          <p className="text-slate-500" style={{ fontSize: "12px" }}>MPC trong vùng</p>
          <p className="text-slate-900 mt-1" style={{ fontSize: "28px", fontWeight: 800 }}>
            {fmt(mpcInBand, 0)}%
          </p>
          <p className="text-slate-400 mt-1" style={{ fontSize: "11px" }}>
            soil moisture nằm trong khoảng
          </p>
        </div>

        <div className="elevated-card rounded-3xl p-5">
          <GitCompare className="w-5 h-5 text-orange-600 mb-4" />
          <p className="text-slate-500" style={{ fontSize: "12px" }}>Rule-based trong vùng</p>
          <p className="text-slate-900 mt-1" style={{ fontSize: "28px", fontWeight: 800 }}>
            {fmt(ruleInBand, 0)}%
          </p>
          <p className="text-slate-400 mt-1" style={{ fontSize: "11px" }}>
            baseline bật/tắt theo ngưỡng
          </p>
        </div>

        <div className="elevated-card rounded-3xl p-5">
          <GitCompare className="w-5 h-5 text-indigo-600 mb-4" />
          <p className="text-slate-500" style={{ fontSize: "12px" }}>Dao động lệnh bơm</p>
          <p className="text-slate-900 mt-1" style={{ fontSize: "24px", fontWeight: 800 }}>
            {fmt(mpcSwitching, 0)}s / {fmt(ruleSwitching, 0)}s
          </p>
          <p className="text-slate-400 mt-1" style={{ fontSize: "11px" }}>
            MPC / rule-based
          </p>
        </div>
      </div>

      <div className="elevated-card rounded-3xl p-5">
        <div className="mb-4">
          <p className="text-slate-800" style={{ fontSize: "16px", fontWeight: 800 }}>
            Khả năng giữ độ ẩm
          </p>
          <p className="text-slate-500" style={{ fontSize: "12px" }}>
            Vùng xanh là khoảng độ ẩm mục tiêu. Đường xanh là MPC, đường xám là độ ẩm đo được.
          </p>
        </div>

        <ResponsiveContainer width="100%" height={320}>
          <ComposedChart data={chartData} margin={{ top: 12, right: 18, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
            <XAxis dataKey="time" tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} domain={yDomain} width={34} />
            <Tooltip />
            <ReferenceArea y1={targetLow} y2={targetHigh} fill="#dcfce7" fillOpacity={0.55} />
            <Line type="monotone" dataKey="actual" name="Độ ẩm đo được" stroke="#94a3b8" strokeWidth={2} dot={{ r: 3 }} />
            <Line type="monotone" dataKey="mpc" name="MPC" stroke="#16a34a" strokeWidth={3} dot={{ r: 4 }} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      <div className="elevated-card rounded-3xl p-5">
        <div className="mb-4">
          <p className="text-slate-800" style={{ fontSize: "16px", fontWeight: 800 }}>
            So sánh MPC với rule-based
          </p>
          <p className="text-slate-500" style={{ fontSize: "12px" }}>
            MPC dự đoán trước và đổi lệnh mềm hơn; rule-based phản ứng theo ngưỡng nên dễ dao động.
          </p>
        </div>

        <ResponsiveContainer width="100%" height={320}>
          <ComposedChart data={chartData} margin={{ top: 12, right: 18, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
            <XAxis dataKey="time" tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} domain={yDomain} width={34} />
            <Tooltip />
            <ReferenceArea y1={targetLow} y2={targetHigh} fill="#dcfce7" fillOpacity={0.45} />
            <Line type="monotone" dataKey="mpc" name="MPC" stroke="#16a34a" strokeWidth={3} dot={{ r: 4 }} />
            <Line type="linear" dataKey="ruleBased" name="Rule-based" stroke="#f97316" strokeWidth={2.6} strokeDasharray="6 4" dot={{ r: 4 }} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      <div className="elevated-card rounded-3xl p-5">
        <p className="text-slate-800" style={{ fontSize: "15px", fontWeight: 800 }}>
          Nhận xét
        </p>
        <p className="text-slate-500 mt-2" style={{ fontSize: "13px" }}>
          Phần này dùng để ghi nhận xét sau khi xem biểu đồ: MPC giữ soil moisture trong khoảng mục tiêu ổn định hơn và ít dao động hơn rule-based.
        </p>
        <p className="text-slate-400 mt-2" style={{ fontSize: "11px" }}>
          Nguồn dữ liệu: {sourceTable}
        </p>
      </div>
    </div>
  );
}
