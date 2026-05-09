import { useState } from "react";
import { Header } from "./components/Header";
import { Sidebar } from "./components/Sidebar";
import { SensorCards } from "./components/SensorCards";
import { DeviceControl } from "./components/DeviceControl";
import { SensorChart } from "./components/SensorChart";
import { SensorHistory } from "./components/SensorHistory";
import { AutoSettings } from "./components/AutoSettings";
import { StatusBar } from "./components/StatusBar";
import { Alerts } from "./components/Alerts";
import { ForecastPage } from "./components/ForecastPage";
import { AuthProvider, useAuth } from "./contexts/AuthContext";
import { LoginPage } from "./pages/LoginPage";
import { RealtimeProvider, useRealtime } from "./contexts/RealtimeContext";

function Dashboard() {
  const { logout } = useAuth();
  const { overview, latest, sensorErrors } = useRealtime();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [activeMenu, setActiveMenu] = useState("dashboard");

  return (
    <div className="min-h-screen relative overflow-hidden">
      <div className="pointer-events-none absolute top-24 right-[12%] h-40 w-40 rounded-full bg-blue-100 blur-3xl animate-float" />
      <div className="pointer-events-none absolute bottom-10 left-1/3 h-44 w-44 rounded-full bg-slate-200/70 blur-3xl animate-pulse-soft" />

      <Header sidebarOpen={sidebarOpen} setSidebarOpen={setSidebarOpen} onLogout={logout} />
      <Sidebar activeMenu={activeMenu} setActiveMenu={setActiveMenu} open={sidebarOpen} />

      <main className="relative pt-20 lg:ml-64 min-h-screen px-4 lg:px-6 pb-6">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
          <div>
            <h2 className="text-slate-900" style={{ fontSize: "24px", fontWeight: 800 }}>
              {activeMenu === "dashboard" && "Tổng quan hệ thống"}
              {activeMenu === "sensors" && "Quản lý cảm biến"}
              {activeMenu === "history" && "Lịch sử cảm biến"}
              {activeMenu === "forecast" && "Dự báo sắp tới"}
              {activeMenu === "devices" && "Điều khiển thiết bị"}
              {activeMenu === "zones" && "Quản lý khu vực"}
              {activeMenu === "charts" && "Biểu đồ & Báo cáo"}
              {activeMenu === "alerts" && "Cảnh báo hệ thống"}
              {activeMenu === "settings" && "Cài đặt hệ thống"}
              {activeMenu === "help" && "Trợ giúp"}
            </h2>
          </div>
        </div>

        {activeMenu === "dashboard" && (
          <div className="space-y-5">
            <StatusBar overview={overview} />

            <section>
              <div className="flex items-center gap-2 mb-3">
                <div className="w-1 h-5 section-kicker rounded-full"></div>
                <h3 className="text-slate-700" style={{ fontSize: "14px", fontWeight: 700 }}>
                  Dữ liệu cảm biến
                </h3>
                <span
                  className="flex items-center gap-1 px-2.5 py-1 bg-blue-50 text-blue-700 rounded-full border border-blue-100"
                  style={{ fontSize: "10px", fontWeight: 700 }}
                >
                  <span className="w-1.5 h-1.5 bg-blue-500 rounded-full animate-pulse-soft"></span>
                  Live
                </span>
              </div>
              <SensorCards data={latest} sensorErrors={sensorErrors} />
            </section>

            <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
              <div className="xl:col-span-2">
                <SensorChart />
              </div>
              <div className="xl:col-span-1">
                <DeviceControl control={overview?.control ?? null} />
              </div>
            </div>

            <AutoSettings />
          </div>
        )}

        {activeMenu === "sensors" && (
          <div className="space-y-5">
            <SensorCards data={latest} />
            <SensorChart />
          </div>
        )}

        {activeMenu === "history" && <SensorHistory />}

        {activeMenu === "forecast" && <ForecastPage />}

        {activeMenu === "devices" && (
          <div className="max-w-lg">
            <DeviceControl control={overview?.control ?? null} />
          </div>
        )}

        {activeMenu === "charts" && <SensorChart />}
        {activeMenu === "settings" && <AutoSettings />}
        {activeMenu === "alerts" && <Alerts />}

        {(activeMenu === "zones" || activeMenu === "help") && (
          <div className="elevated-card rounded-3xl p-10 text-center">
            <div className="w-16 h-16 bg-slate-50 rounded-2xl flex items-center justify-center mx-auto mb-3 border border-slate-200 animate-float">
              <span className="text-3xl">✨</span>
            </div>
            <p className="text-slate-700" style={{ fontSize: "15px", fontWeight: 700 }}>
              Tính năng đang phát triển
            </p>
            <p className="text-slate-500 mt-1" style={{ fontSize: "13px" }}>
              Chức năng này sẽ sớm được ra mắt
            </p>
          </div>
        )}
      </main>
    </div>
  );
}

function AppInner() {
  const { isAuthenticated } = useAuth();

  return isAuthenticated ? (
    <RealtimeProvider>
      <Dashboard />
    </RealtimeProvider>
  ) : (
    <LoginPage />
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppInner />
    </AuthProvider>
  );
}