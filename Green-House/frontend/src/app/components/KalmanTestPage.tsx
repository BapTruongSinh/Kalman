import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  GitCompare,
  RefreshCw,
  Sparkles,
  TrendingDown,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  ComposedChart,
} from "recharts";
import { EstimationCycle, getKalmanTestSeries } from "../api/endpoints";
import { Button } from "./ui/button";

type KalmanChartPoint = {
  time: string;
  raw: number | null;
  filtered: number | null;
  innovation: number | null;
  delta: number | null;
};

function fmt(value: number | null | undefined, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) {
    return "--";
  }
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

function finiteValues(values: Array<number | null | undefined>) {
  return values.filter((value): value is number => Number.isFinite(value));
}

function varianceOfDiff(values: number[]) {
  if (values.length < 3) return null;
  const diffs = values.slice(1).map((value, index) => value - values[index]);
  const mean = diffs.reduce((sum, value) => sum + value, 0) / diffs.length;
  return diffs.reduce((sum, value) => sum + (value - mean) ** 2, 0) / diffs.length;
}

function meanAbsoluteCorrection(rows: EstimationCycle[]) {
  const corrections = rows
    .map((row) => {
      if (row.raw_soil_moisture === null || row.kf_x_posterior === null) return null;
      return Math.abs(row.raw_soil_moisture - row.kf_x_posterior);
    })
    .filter((value): value is number => value !== null);

  if (!corrections.length) return null;
  return corrections.reduce((sum, value) => sum + value, 0) / corrections.length;
}

function downsample<T>(rows: T[], maxPoints: number) {
  if (rows.length <= maxPoints) return rows;
  const step = Math.ceil(rows.length / maxPoints);
  return rows.filter((_, index) => index % step === 0);
}

function latestWindow<T>(rows: T[], maxRows: number) {
  if (rows.length <= maxRows) return rows;
  return rows.slice(rows.length - maxRows);
}

export function KalmanTestPage() {
  const [cycles, setCycles] = useState<EstimationCycle[]>([]);
  const [source, setSource] = useState({ database: "kalman_greenhouse", table: "pipeline_cycles" });
  const [selectedCount, setSelectedCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const response = await getKalmanTestSeries(100000);
      setCycles(response.data.points);
      setSource({
        database: response.data.source_database,
        table: response.data.source_table,
      });
      setSelectedCount(response.data.total_selected);
      if (response.data.total_selected === 0) {
        setError("Database kalman_greenhouse chưa có mẫu pipeline_cycles hợp lệ.");
      }
    } catch {
      setError("Không tải được dữ liệu từ kalman_greenhouse.pipeline_cycles.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const validCycles = useMemo(
    () =>
      cycles.filter(
        (row) =>
          row.raw_soil_moisture !== null &&
          row.kf_x_posterior !== null &&
          row.cycle_status === "ok"
      ),
    [cycles]
  );

  const chartData = useMemo<KalmanChartPoint[]>(
    () =>
      downsample(latestWindow(validCycles, 1000), 1000).map((row) => ({
        time: timeLabel(row.sample_ts),
        raw: row.raw_soil_moisture,
        filtered: row.kf_x_posterior,
        innovation: row.kf_innovation ?? null,
        delta:
          row.raw_soil_moisture === null || row.kf_x_posterior === null
            ? null
            : row.raw_soil_moisture - row.kf_x_posterior,
      })),
    [validCycles]
  );

  const yDomain = useMemo<[number, number]>(() => {
    const values = chartData.flatMap((row) =>
      [row.raw, row.filtered].filter((value): value is number => Number.isFinite(value))
    );
    if (!values.length) return [0, 100];
    const min = Math.min(...values);
    const max = Math.max(...values);
    const padding = Math.max(2, (max - min) * 0.18);
    return [Math.max(0, Math.floor(min - padding)), Math.min(100, Math.ceil(max + padding))];
  }, [chartData]);

  const rawVariance = varianceOfDiff(finiteValues(validCycles.map((row) => row.raw_soil_moisture)));
  const filteredVariance = varianceOfDiff(finiteValues(validCycles.map((row) => row.kf_x_posterior)));
  const varianceReduction =
    rawVariance !== null && rawVariance > 0 && filteredVariance !== null
      ? (1 - filteredVariance / rawVariance) * 100
      : null;
  const avgCorrection = meanAbsoluteCorrection(validCycles);

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-slate-500" style={{ fontSize: "12px", fontWeight: 700 }}>
            Kalman Filter test
          </p>
          <p className="text-slate-900" style={{ fontSize: "22px", fontWeight: 800 }}>
            Đánh giá Kalman Filter
          </p>
          <p className="text-slate-500 mt-1" style={{ fontSize: "13px" }}>
            So sánh tín hiệu trước lọc và sau lọc từ database Kalman
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
          <Activity className="w-5 h-5 text-blue-600 mb-4" />
          <p className="text-slate-500" style={{ fontSize: "12px" }}>Run đang đánh giá</p>
          <p className="text-slate-900 mt-1 truncate" style={{ fontSize: "18px", fontWeight: 800 }}>
            {source.database}
          </p>
          <p className="text-slate-400 mt-1" style={{ fontSize: "11px" }}>
            {source.table}
          </p>
        </div>

        <div className="elevated-card rounded-3xl p-5">
          <GitCompare className="w-5 h-5 text-emerald-600 mb-4" />
          <p className="text-slate-500" style={{ fontSize: "12px" }}>Số mẫu hợp lệ</p>
          <p className="text-slate-900 mt-1" style={{ fontSize: "28px", fontWeight: 800 }}>
            {selectedCount.toLocaleString("vi-VN")}
          </p>
          <p className="text-slate-400 mt-1" style={{ fontSize: "11px" }}>
            vẽ đại diện {chartData.length.toLocaleString("vi-VN")} điểm
          </p>
        </div>

        <div className="elevated-card rounded-3xl p-5">
          <TrendingDown className="w-5 h-5 text-orange-600 mb-4" />
          <p className="text-slate-500" style={{ fontSize: "12px" }}>Giảm dao động</p>
          <p className="text-slate-900 mt-1" style={{ fontSize: "28px", fontWeight: 800 }}>
            {fmt(varianceReduction, 1)}%
          </p>
          <p className="text-slate-400 mt-1" style={{ fontSize: "11px" }}>
            variance của sai phân trước/sau lọc
          </p>
        </div>

        <div className="elevated-card rounded-3xl p-5">
          <Sparkles className="w-5 h-5 text-indigo-600 mb-4" />
          <p className="text-slate-500" style={{ fontSize: "12px" }}>Hiệu chỉnh trung bình</p>
          <p className="text-slate-900 mt-1" style={{ fontSize: "28px", fontWeight: 800 }}>
            {fmt(avgCorrection, 2)}%
          </p>
          <p className="text-slate-400 mt-1" style={{ fontSize: "11px" }}>
            |trước lọc - sau lọc|
          </p>
        </div>
      </div>

      <div className="elevated-card rounded-3xl p-5">
        <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
          <div>
            <p className="text-slate-800" style={{ fontSize: "16px", fontWeight: 800 }}>
              So sánh trước lọc và sau lọc
            </p>
            <p className="text-slate-500" style={{ fontSize: "12px" }}>
              Hai biểu đồ dùng cùng trục Y và lấy 1000 mẫu mới nhất để dễ nhìn mức giảm nhiễu.
            </p>
          </div>
        </div>

        {chartData.length === 0 ? (
          <div className="flex h-80 items-center justify-center text-slate-400" style={{ fontSize: "13px" }}>
            Chưa có dữ liệu Kalman hợp lệ để vẽ biểu đồ.
          </div>
        ) : (
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
            <div className="rounded-2xl border border-blue-100 bg-blue-50/30 p-4">
              <div className="mb-3">
                <p className="text-blue-700" style={{ fontSize: "14px", fontWeight: 800 }}>
                  Trước lọc - dữ liệu sensor thô
                </p>
                <p className="text-slate-500" style={{ fontSize: "12px" }}>
                  Dao động trực tiếp theo mẫu đo.
                </p>
              </div>
              <ResponsiveContainer width="100%" height={300}>
                <ComposedChart data={chartData} margin={{ top: 12, right: 18, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#dbeafe" vertical={false} />
                  <XAxis dataKey="time" tick={{ fontSize: 10, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 10, fill: "#94a3b8" }} axisLine={false} tickLine={false} domain={yDomain} width={34} />
                  <Tooltip />
                  <Line
                    type="linear"
                    dataKey="raw"
                    name="Trước lọc"
                    stroke="#2563eb"
                    strokeWidth={2.4}
                    dot={false}
                    activeDot={{ r: 5, fill: "#2563eb", stroke: "#ffffff", strokeWidth: 2 }}
                    isAnimationActive={false}
                  />
                </ComposedChart>
              </ResponsiveContainer>
            </div>

            <div className="rounded-2xl border border-red-100 bg-red-50/30 p-4">
              <div className="mb-3">
                <p className="text-red-700" style={{ fontSize: "14px", fontWeight: 800 }}>
                  Sau lọc - Kalman Filter
                </p>
                <p className="text-slate-500" style={{ fontSize: "12px" }}>
                  Ước lượng sau lọc, dùng để đánh giá độ mượt.
                </p>
              </div>
              <ResponsiveContainer width="100%" height={300}>
                <ComposedChart data={chartData} margin={{ top: 12, right: 18, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#fee2e2" vertical={false} />
                  <XAxis dataKey="time" tick={{ fontSize: 10, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 10, fill: "#94a3b8" }} axisLine={false} tickLine={false} domain={yDomain} width={34} />
                  <Tooltip />
                  <Line
                    type="monotone"
                    dataKey="filtered"
                    name="Sau lọc"
                    stroke="#ef4444"
                    strokeWidth={2.4}
                    dot={false}
                    activeDot={{ r: 5, fill: "#ef4444", stroke: "#ffffff", strokeWidth: 2 }}
                    isAnimationActive={false}
                  />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}
      </div>

      <div className="elevated-card rounded-3xl p-5">
        <div className="mb-4">
          <p className="text-slate-800" style={{ fontSize: "16px", fontWeight: 800 }}>
            Sai khác giữa trước lọc và sau lọc
          </p>
          <p className="text-slate-500" style={{ fontSize: "12px" }}>
            Cột dương nghĩa là sensor thô cao hơn Kalman; cột âm nghĩa là sensor thô thấp hơn Kalman.
          </p>
        </div>

        <ResponsiveContainer width="100%" height={180}>
          <BarChart data={chartData} margin={{ top: 8, right: 18, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
            <XAxis dataKey="time" tick={{ fontSize: 10, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fontSize: 10, fill: "#94a3b8" }} axisLine={false} tickLine={false} width={34} />
            <Tooltip />
            <Bar dataKey="delta" name="Trước lọc - Sau lọc" fill="#2563eb" radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="elevated-card rounded-3xl p-5">
        <p className="text-slate-800" style={{ fontSize: "15px", fontWeight: 800 }}>
          Nhận xét
        </p>
        <p className="text-slate-500 mt-2" style={{ fontSize: "13px" }}>
          Phần này sẽ dùng để ghi nhận xét sau khi có kết quả test: Kalman Filter giảm nhiễu và làm tín hiệu mượt hơn hay không.
        </p>
      </div>
    </div>
  );
}
