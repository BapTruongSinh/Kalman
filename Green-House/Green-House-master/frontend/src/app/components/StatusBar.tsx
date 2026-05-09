import { CheckCircle, AlertTriangle, Clock, Wifi, WifiOff, Bot, Hand } from "lucide-react";
import type { DashboardOverview } from "../contexts/RealtimeContext";

interface StatusBarProps {
  overview: DashboardOverview | null;
}

export function StatusBar({ overview }: StatusBarProps) {
  const backendReachable = overview !== null;
  const unreadAlerts = overview?.unread_alerts ?? 0;
  const onlineDevices = overview?.online_devices ?? 0;
  const deviceCount = overview?.device_count ?? 0;
  const uptimeHint = overview?.uptime_hint ?? "—";
  const mode = overview?.control?.mode ?? "AUTO";
  const esp32Online = overview?.esp32_online ?? false;

  const systemAlerts = [
    {
      type: esp32Online ? "ok" : "warn",
      message: esp32Online ? "ESP32 đang kết nối" : "ESP32 đang offline",
    },
    {
      type: unreadAlerts > 0 ? "warn" : "ok",
      message: unreadAlerts > 0 ? `${unreadAlerts} cảnh báo chưa đọc` : "Không có cảnh báo mới",
    },
    {
      type: mode === "AUTO" ? "ok" : "warn",
      message: mode === "AUTO" ? "Hệ thống đang chạy AUTO" : "Hệ thống đang ở MANUAL",
    },
  ];

  const stats = [
    { label: "Uptime", value: uptimeHint, icon: Clock },
    { label: "Mode", value: mode, icon: mode === "AUTO" ? Bot : Hand },
  ];

  return (
    <div className="flex flex-wrap gap-3 mb-5">
      <div className="flex-1 min-w-0 elevated-card rounded-3xl p-4">
        <p
          className="text-slate-400 mb-2.5"
          style={{ fontSize: "11px", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.05em" }}
        >
          System status
        </p>

        <div className="space-y-2">
          {systemAlerts.map((alert, i) => (
            <div key={i} className="flex items-center gap-2">
              {alert.type === "ok" ? (
                <CheckCircle className="w-3.5 h-3.5 text-blue-500 flex-shrink-0" />
              ) : (
                <AlertTriangle className="w-3.5 h-3.5 text-amber-500 flex-shrink-0" />
              )}
              <span className="text-slate-600" style={{ fontSize: "12px" }}>
                {alert.message}
              </span>
            </div>
          ))}
        </div>
      </div>

      <div className="flex gap-3">
        {stats.map((stat) => {
          const Icon = stat.icon;
          return (
            <div
              key={stat.label}
              className="elevated-card rounded-3xl p-4 flex flex-col items-center justify-center min-w-[110px] text-center hover-lift"
            >
              <Icon className="w-4 h-4 text-blue-600 mb-1" />
              <p className="text-slate-900" style={{ fontSize: "16px", fontWeight: 700 }}>
                {overview ? stat.value : <span className="text-slate-300">—</span>}
              </p>
              <p className="text-slate-400" style={{ fontSize: "10px" }}>
                {stat.label}
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
}