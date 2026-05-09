import { AlertTriangle, Bell, CheckCircle, Info, X } from "lucide-react";
import { useState } from "react";
import { useRealtime } from "../contexts/RealtimeContext";

function timeAgo(dateString: string) {
  const diff = Date.now() - new Date(dateString).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "Vừa xong";
  if (mins < 60) return `${mins} phút trước`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs} giờ trước`;
  return `${Math.floor(hrs / 24)} ngày trước`;
}

export function Alerts() {
  const { alerts, markAlertRead, markAllAlertsRead } = useRealtime();
  const [filter, setFilter] = useState<"all" | "unread">("all");
  const [dismissed, setDismissed] = useState<number[]>([]);

  const visibleAlerts = alerts.filter((a) => !dismissed.includes(a.id));
  const filteredAlerts = filter === "all" ? visibleAlerts : visibleAlerts.filter((a) => !a.is_read);
  const unreadCount = visibleAlerts.filter((a) => !a.is_read).length;

  const getAlertIcon = (level: string) => {
    switch (level) {
      case "warning":
        return <AlertTriangle className="w-5 h-5 text-amber-500" />;
      case "error":
        return <AlertTriangle className="w-5 h-5 text-red-500" />;
      case "success":
        return <CheckCircle className="w-5 h-5 text-blue-500" />;
      case "info":
        return <Info className="w-5 h-5 text-slate-500" />;
      default:
        return <Bell className="w-5 h-5 text-slate-500" />;
    }
  };

  const getAlertColor = (level: string) => {
    switch (level) {
      case "warning":
        return "border-amber-200 bg-amber-50";
      case "error":
        return "border-red-200 bg-red-50";
      case "success":
        return "border-blue-200 bg-blue-50";
      default:
        return "border-slate-200 bg-slate-50";
    }
  };

  return (
    <div className="space-y-4">
      <div className="elevated-card rounded-3xl p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-blue-50 rounded-xl flex items-center justify-center border border-blue-100">
              <Bell className="w-5 h-5 text-blue-600" />
            </div>
            <div>
              <h3 className="text-slate-900" style={{ fontSize: "16px", fontWeight: 700 }}>
                Trung tâm cảnh báo
              </h3>
              <p className="text-slate-500" style={{ fontSize: "12px" }}>
                {unreadCount} cảnh báo chưa đọc
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setFilter("all")}
              className={`px-3 py-1.5 rounded-lg border transition-colors ${
                filter === "all"
                  ? "bg-blue-50 text-blue-700 border-blue-100"
                  : "bg-slate-50 text-slate-600 border-slate-200 hover:bg-slate-100"
              }`}
              style={{ fontSize: "12px", fontWeight: 600 }}
            >
              Tất cả ({visibleAlerts.length})
            </button>

            <button
              onClick={() => setFilter("unread")}
              className={`px-3 py-1.5 rounded-lg border transition-colors ${
                filter === "unread"
                  ? "bg-blue-50 text-blue-700 border-blue-100"
                  : "bg-slate-50 text-slate-600 border-slate-200 hover:bg-slate-100"
              }`}
              style={{ fontSize: "12px", fontWeight: 600 }}
            >
              Chưa đọc ({unreadCount})
            </button>

            {unreadCount > 0 && (
              <button
                onClick={markAllAlertsRead}
                className="px-3 py-1.5 gradient-action text-white rounded-lg"
                style={{ fontSize: "12px", fontWeight: 600 }}
              >
                Đánh dấu tất cả đã đọc
              </button>
            )}
          </div>
        </div>
      </div>

      <div className="space-y-3">
        {filteredAlerts.length === 0 ? (
          <div className="elevated-card rounded-3xl p-8 text-center">
            <div className="w-16 h-16 bg-slate-50 rounded-2xl border border-slate-200 flex items-center justify-center mx-auto mb-3">
              <Bell className="w-8 h-8 text-slate-300" />
            </div>
            <p className="text-slate-700" style={{ fontSize: "15px", fontWeight: 600 }}>
              Không có cảnh báo
            </p>
            <p className="text-slate-400 mt-1" style={{ fontSize: "13px" }}>
              Tất cả cảnh báo đã được xử lý
            </p>
          </div>
        ) : (
          filteredAlerts.map((alert) => (
            <div
              key={alert.id}
              className={`elevated-card rounded-3xl p-4 transition-all hover:shadow-md ${
                !alert.is_read ? getAlertColor(alert.level) : ""
              }`}
            >
              <div className="flex items-start gap-3">
                <div className="flex-shrink-0 mt-0.5">{getAlertIcon(alert.level)}</div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between gap-2 mb-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h4
                        className={`${!alert.is_read ? "text-slate-900" : "text-slate-700"}`}
                        style={{ fontSize: "14px", fontWeight: !alert.is_read ? 700 : 600 }}
                      >
                        {alert.title}
                      </h4>
                      {!alert.is_read && <span className="w-2 h-2 bg-blue-500 rounded-full"></span>}
                    </div>

                    <button
                      onClick={() => setDismissed((prev) => [...prev, alert.id])}
                      className="flex-shrink-0 p-1 hover:bg-white/70 rounded-lg transition-colors"
                    >
                      <X className="w-4 h-4 text-slate-400" />
                    </button>
                  </div>

                  <p className="text-slate-600 mb-2" style={{ fontSize: "13px", lineHeight: "1.5" }}>
                    {alert.message}
                  </p>

                  <div className="flex items-center gap-3 flex-wrap">
                    <span className="text-slate-400" style={{ fontSize: "11px" }}>
                      🕐 {timeAgo(alert.happened_at)}
                    </span>
                    <span className="text-slate-400 capitalize" style={{ fontSize: "11px" }}>
                      🔔 {alert.level}
                    </span>

                    {!alert.is_read && (
                      <button
                        onClick={() => markAlertRead(alert.id)}
                        className="text-blue-600 hover:text-blue-700 ml-auto"
                        style={{ fontSize: "11px", fontWeight: 600 }}
                      >
                        Đánh dấu đã đọc
                      </button>
                    )}
                  </div>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}