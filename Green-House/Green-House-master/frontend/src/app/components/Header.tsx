import { Bell, Wifi, RefreshCw, LogOut, LayoutGrid } from "lucide-react";
import { useState } from "react";

interface HeaderProps {
  sidebarOpen: boolean;
  setSidebarOpen: (open: boolean) => void;
  onLogout?: () => void;
}

export function Header({ sidebarOpen, setSidebarOpen, onLogout }: HeaderProps) {
  const [showUserMenu, setShowUserMenu] = useState(false);
  const now = new Date();
  const timeStr = now.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" });
  const dateStr = now.toLocaleDateString("vi-VN", { weekday: "long", year: "numeric", month: "long", day: "numeric" });

  return (
    <header className="fixed top-0 left-0 lg:left-64 right-0 h-16 border-b border-slate-200 bg-white/90 backdrop-blur-sm flex items-center justify-between px-4 lg:px-6 z-30">
      <div className="flex items-center gap-3">
        <button
          onClick={() => setSidebarOpen(!sidebarOpen)}
          className="p-2 rounded-xl hover:bg-slate-100 transition-colors lg:hidden"
        >
          <div className="w-5 h-0.5 bg-slate-600 mb-1"></div>
          <div className="w-5 h-0.5 bg-slate-600 mb-1"></div>
          <div className="w-5 h-0.5 bg-slate-600"></div>
        </button>
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-2xl bg-blue-600 flex items-center justify-center shadow-sm">
            <LayoutGrid className="w-4 h-4 text-white" />
          </div>
          <div>
            <h1 className="text-slate-900" style={{ fontSize: "15px", fontWeight: 700, lineHeight: 1.2 }}>Smart Greenhouse</h1>
          </div>
        </div>
      </div>

      <div className="hidden md:flex flex-col items-center">
        <span className="text-slate-800" style={{ fontSize: "15px", fontWeight: 600 }}>{timeStr}</span>
        <span className="text-slate-500" style={{ fontSize: "11px" }}>{dateStr}</span>
      </div>

      <div className="flex items-center gap-2">
        <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium border border-blue-100 bg-blue-50 text-blue-700">
          <Wifi className="w-3.5 h-3.5" />
          {/* <span style={{ fontSize: "12px" }}>Trực tuyến</span> */}
          {/* <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse-soft"></span> */}
        </div>

        {/* <button className="p-2 rounded-xl hover:bg-slate-100 text-slate-500 hover:text-blue-600 transition-colors">
          <RefreshCw className="w-4 h-4" />
        </button> */}

        <button className="relative p-2 rounded-xl hover:bg-slate-100 text-slate-500 hover:text-blue-600 transition-colors">
          <Bell className="w-4 h-4" />
          <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-red-500 rounded-full border border-white"></span>
        </button>

        <div className="relative">
          <button
            onClick={() => setShowUserMenu(!showUserMenu)}
            className="flex items-center gap-2 px-2.5 py-1.5 rounded-xl hover:bg-slate-100 transition-colors border border-transparent hover:border-slate-200"
          >
            <div className="w-8 h-8 bg-slate-900 rounded-full flex items-center justify-center">
              <span className="text-white" style={{ fontSize: "12px", fontWeight: 700 }}>A</span>
            </div>
            <span className="hidden sm:block text-slate-700" style={{ fontSize: "13px", fontWeight: 500 }}>Admin</span>
          </button>

          {showUserMenu && (
            <div className="absolute right-0 top-full mt-2 w-44 bg-white border border-slate-200 rounded-2xl shadow-lg py-1 z-50">
              <button
                onClick={() => { setShowUserMenu(false); onLogout?.(); }}
                className="w-full flex items-center gap-2 px-4 py-2.5 text-left hover:bg-red-50 text-red-600 transition-colors rounded-2xl"
                style={{ fontSize: "13px", fontWeight: 600 }}
              >
                <LogOut className="w-4 h-4" />
                Đăng xuất
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
