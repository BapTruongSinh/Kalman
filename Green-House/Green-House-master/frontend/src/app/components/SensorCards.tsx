import { Thermometer, Droplets, Sun, Sprout, TrendingUp, TrendingDown, Minus, AlertTriangle } from "lucide-react";
import type { SensorErrors, SensorReading } from "../lib/websocket";

interface SensorCardsProps {
  data: SensorReading | null;
  sensorErrors?: SensorErrors;
}

type TrendType = "up" | "down" | "stable";

interface CardConfig {
  label: string;
  apiKey: keyof SensorReading;
  errorKey: keyof SensorErrors;
  unit: string;
  icon: React.ElementType;
  iconBg: string;
  iconColor: string;
  progressColor: string;
  min: number;
  max: number;
  optimal: { min: number; max: number };
  trend: TrendType;
  trendVal: string;
}

const cardConfigs: CardConfig[] = [
  {
    label: "Nhiệt độ",
    apiKey: "temperature",
    errorKey: "dht",
    unit: "°C",
    icon: Thermometer,
    iconBg: "bg-orange-50",
    iconColor: "text-orange-500",
    progressColor: "#f97316",
    min: 15,
    max: 45,
    optimal: { min: 22, max: 32 },
    trend: "up",
    trendVal: "+0.8",
  },
  {
    label: "Độ ẩm không khí",
    apiKey: "humidity",
    errorKey: "dht",
    unit: "%",
    icon: Droplets,
    iconBg: "bg-blue-50",
    iconColor: "text-blue-500",
    progressColor: "#2563eb",
    min: 0,
    max: 100,
    optimal: { min: 60, max: 80 },
    trend: "stable",
    trendVal: "0.0",
  },
  {
    label: "Ánh sáng",
    apiKey: "light",
    errorKey: "light",
    unit: "%",
    icon: Sun,
    iconBg: "bg-amber-50",
    iconColor: "text-amber-500",
    progressColor: "#eab308",
    min: 0,
    max: 100,
    optimal: { min: 30, max: 80 },
    trend: "down",
    trendVal: "-1.2",
  },
  {
    label: "Độ ẩm đất",
    apiKey: "soil_moisture",
    errorKey: "soil",
    unit: "%",
    icon: Sprout,
    iconBg: "bg-violet-50",
    iconColor: "text-violet-500",
    progressColor: "#8b5cf6",
    min: 0,
    max: 100,
    optimal: { min: 60, max: 80 },
    trend: "up",
    trendVal: "+2.3",
  },
];

function TrendIcon({ trend }: { trend: TrendType }) {
  if (trend === "up") return <TrendingUp className="w-3 h-3" />;
  if (trend === "down") return <TrendingDown className="w-3 h-3" />;
  return <Minus className="w-3 h-3" />;
}

function getStatus(value: number, optimal: { min: number; max: number }) {
  if (value < optimal.min) {
    return { label: "Thấp", color: "text-blue-700 bg-blue-50 border-blue-100" };
  }
  if (value > optimal.max) {
    return { label: "Cao", color: "text-red-700 bg-red-50 border-red-100" };
  }
  return { label: "Tối ưu", color: "text-slate-700 bg-slate-100 border-slate-200" };
}

function toNumberOrNull(value: unknown): number | null {
  if (value === null || value === undefined) return null;

  if (typeof value === "number") {
    return Number.isFinite(value) ? value : null;
  }

  if (typeof value === "string") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }

  return null;
}

function formatValue(value: unknown) {
  const num = toNumberOrNull(value);
  return num === null ? "—" : num.toFixed(1);
}

const defaultSensorErrors: SensorErrors = {
  dht: false,
  soil: false,
  light: false,
  gas: false,
};

export function SensorCards({ data, sensorErrors = defaultSensorErrors }: SensorCardsProps) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
      {cardConfigs.map((card) => {
        const Icon = card.icon;

        const rawValue = data ? data[card.apiKey] : null;
        const numericValue = toNumberOrNull(rawValue);
        const isError = !!sensorErrors[card.errorKey];
        const hasData = numericValue !== null && !isError;
        const value = numericValue ?? 0;

        const percent = hasData
          ? Math.min(100, Math.max(0, ((value - card.min) / (card.max - card.min)) * 100))
          : 0;

        const status = hasData ? getStatus(value, card.optimal) : null;
        const trendColor =
          card.trend === "up"
            ? "text-blue-600"
            : card.trend === "down"
              ? "text-red-500"
              : "text-slate-500";

        return (
          <div key={String(card.apiKey)} className="elevated-card rounded-3xl p-5 hover-lift relative overflow-hidden">
            <div className="flex items-start justify-between mb-4">
              <div>
                <p className="text-slate-500" style={{ fontSize: "12px", fontWeight: 500 }}>
                  {card.label}
                </p>

                <div className="flex items-end gap-1 mt-1">
                  {hasData ? (
                    <>
                      <span className="text-slate-900" style={{ fontSize: "28px", fontWeight: 700, lineHeight: 1 }}>
                        {formatValue(value)}
                      </span>
                      <span className="text-slate-500 pb-0.5" style={{ fontSize: "14px" }}>
                        {card.unit}
                      </span>
                    </>
                  ) : (
                    <span className="text-slate-300" style={{ fontSize: "28px", fontWeight: 700, lineHeight: 1 }}>
                      —
                    </span>
                  )}
                </div>
              </div>

              <div className={`w-11 h-11 ${card.iconBg} rounded-2xl flex items-center justify-center flex-shrink-0 border border-slate-100`}>
                <Icon className={`w-5 h-5 ${card.iconColor}`} />
              </div>
            </div>

            <div className="mb-3">
              <div className="flex justify-between mb-1">
                <span className="text-slate-400" style={{ fontSize: "10px" }}>
                  {card.min}{card.unit}
                </span>
                <span className="text-slate-400" style={{ fontSize: "10px" }}>
                  {card.max}{card.unit}
                </span>
              </div>

              <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-700"
                  style={{ width: `${percent}%`, background: card.progressColor }}
                />
              </div>
            </div>

            <div className="flex items-center justify-between mt-4">
              {isError ? (
                <span
                  className="px-2.5 py-1 rounded-full border border-red-100 bg-red-50 text-red-700 inline-flex items-center gap-1.5"
                  style={{ fontSize: "11px", fontWeight: 600 }}
                >
                  <AlertTriangle className="w-3 h-3" />
                  Lỗi cảm biến
                </span>
              ) : status ? (
                <span
                  className={`px-2.5 py-1 rounded-full border ${status.color}`}
                  style={{ fontSize: "11px", fontWeight: 600 }}
                >
                  {status.label}
                </span>
              ) : (
                <span
                  className="px-2.5 py-1 rounded-full border border-slate-200 bg-slate-50 text-slate-400 animate-pulse"
                  style={{ fontSize: "11px" }}
                >
                  Đang tải...
                </span>
              )}

              {/* <span className={`flex items-center gap-1 ${trendColor}`} style={{ fontSize: "11px", fontWeight: 600 }}>
                <TrendIcon trend={card.trend} />
                {card.trendVal}
              </span> */}
            </div>
          </div>
        );
      })}
    </div>
  );
}