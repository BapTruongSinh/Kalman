import { useMemo, useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import { BarChart3, Clock } from "lucide-react";
import { useRealtime } from "../contexts/RealtimeContext";

interface ChartDataPoint {
  time: string;
  temperature?: number;
  humidity?: number;
  light?: number;
  soil_moisture?: number;
}

const sensors = [
  { key: "temperature", label: "Nhiệt độ (°C)", color: "#f97316" },
  { key: "humidity", label: "Độ ẩm KK (%)", color: "#2563eb" },
  { key: "light", label: "Ánh sáng (%)", color: "#eab308" },
  { key: "soil_moisture", label: "Độ ẩm đất (%)", color: "#8b5cf6" },
] as const;

function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;

  return (
    <div className="bg-white border border-slate-200 rounded-2xl shadow-lg p-3 min-w-[160px]">
      <p
        className="text-slate-500 mb-2 flex items-center gap-1.5"
        style={{ fontSize: "11px", fontWeight: 600 }}
      >
        <Clock className="w-3 h-3" />
        {label}
      </p>

      {payload.map((entry: any) => (
        <div key={entry.dataKey} className="flex items-center justify-between gap-4 mb-1">
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: entry.color }}></span>
            <span className="text-slate-600" style={{ fontSize: "11px" }}>
              {entry.name}
            </span>
          </div>
          <span style={{ fontSize: "12px", fontWeight: 700, color: entry.color }}>{entry.value}</span>
        </div>
      ))}
    </div>
  );
}

export function SensorChart() {
  const { chartHistory } = useRealtime();
  const [activeSensors, setActiveSensors] = useState<string[]>([
    "temperature",
    "humidity",
    "light",
    "soil_moisture",
  ]);

  const chartData = useMemo<ChartDataPoint[]>(
    () =>
      chartHistory.map((p) => ({
        time: new Date(p.recorded_at).toLocaleTimeString("vi-VN", {
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
          hour12: false,
        }),
        temperature: p.temperature ?? undefined,
        humidity: p.humidity ?? undefined,
        light: p.light ?? undefined,
        soil_moisture: p.soil_moisture ?? undefined,
      })),
    [chartHistory]
  );

  const toggleSensor = (key: string) => {
    setActiveSensors((prev) =>
      prev.includes(key) ? (prev.length > 1 ? prev.filter((s) => s !== key) : prev) : [...prev, key]
    );
  };

  return (
    <div className="elevated-card rounded-3xl overflow-hidden">
      <div className="px-5 py-4 border-b border-slate-200">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 bg-blue-50 rounded-xl flex items-center justify-center border border-blue-100">
              <BarChart3 className="w-4 h-4 text-blue-600" />
            </div>
            <div>
              <h3 className="text-slate-900">Dữ liệu cảm biến</h3>
            </div>
          </div>
        </div>

        <div className="flex flex-wrap gap-2 mt-3">
          {sensors.map((sensor) => (
            <button
              key={sensor.key}
              onClick={() => toggleSensor(sensor.key)}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border transition-all duration-200 ${
                activeSensors.includes(sensor.key)
                  ? "shadow-sm bg-white"
                  : "border-slate-200 bg-slate-50 opacity-60"
              }`}
              style={{
                borderColor: activeSensors.includes(sensor.key) ? `${sensor.color}33` : undefined,
              }}
            >
              <span
                className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                style={{ background: sensor.color }}
              ></span>
              <span
                style={{
                  fontSize: "11px",
                  fontWeight: 600,
                  color: activeSensors.includes(sensor.key) ? "#0f172a" : "#94a3b8",
                }}
              >
                {sensor.label}
              </span>
            </button>
          ))}
        </div>
      </div>

      <div className="p-5">
        {chartData.length === 0 ? (
          <div className="flex items-center justify-center h-64 text-slate-400" style={{ fontSize: "13px" }}>
            Chưa có dữ liệu từ ESP
          </div>
        ) : (
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={chartData} margin={{ top: 5, right: 10, left: -10, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
              <XAxis
                dataKey="time"
                tick={{ fontSize: 10, fill: "#94a3b8" }}
                axisLine={false}
                tickLine={false}
                dy={4}
              />
              <YAxis
                yAxisId="left"
                tick={{ fontSize: 10, fill: "#94a3b8" }}
                axisLine={false}
                tickLine={false}
                domain={[0, 100]}
              />
              <Tooltip content={<CustomTooltip />} />
              <ReferenceLine yAxisId="left" y={80} stroke="#cbd5e1" strokeDasharray="4 4" />
              <ReferenceLine yAxisId="left" y={60} stroke="#cbd5e1" strokeDasharray="4 4" />

              {sensors.map((sensor) =>
                activeSensors.includes(sensor.key) ? (
                  <Line
                    key={sensor.key}
                    yAxisId="left"
                    type="monotone"
                    dataKey={sensor.key}
                    name={sensor.label}
                    stroke={sensor.color}
                    strokeWidth={2.5}
                    dot={false}
                    activeDot={{ r: 4, fill: sensor.color, stroke: "white", strokeWidth: 2 }}
                  />
                ) : null
              )}
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}