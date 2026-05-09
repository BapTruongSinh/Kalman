import { useState, FormEvent } from "react";
import { useAuth } from "../contexts/AuthContext";
import { Leaf, AlertCircle } from "lucide-react";

export function LoginPage() {
  const { login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(username, password);
    } catch {
      setError("Tên đăng nhập hoặc mật khẩu không đúng.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center relative overflow-hidden">
      <div className="pointer-events-none absolute top-20 right-[15%] h-72 w-72 rounded-full bg-blue-100 blur-3xl opacity-60" />
      <div className="pointer-events-none absolute bottom-20 left-[10%] h-64 w-64 rounded-full bg-slate-200 blur-3xl opacity-60" />

      <div className="elevated-card rounded-3xl p-10 w-full max-w-sm relative z-10">
        <div className="flex flex-col items-center mb-8">
          <div className="w-14 h-14 gradient-action rounded-2xl flex items-center justify-center mb-4 shadow-lg">
            <Leaf className="w-7 h-7 text-white" />
          </div>
          <h1 className="text-slate-900" style={{ fontSize: "22px", fontWeight: 800 }}>
            Smart Greenhouse
          </h1>
          <p className="text-slate-500 mt-1" style={{ fontSize: "13px" }}>
            Đăng nhập để quản lý nhà kính
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-slate-700 mb-1.5" style={{ fontSize: "13px", fontWeight: 600 }}>
              Tên đăng nhập
            </label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              autoFocus
              className="w-full px-4 py-2.5 rounded-xl border border-slate-200 bg-slate-50 text-slate-900 outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100 transition-all"
              style={{ fontSize: "14px" }}
              placeholder="admin"
            />
          </div>

          <div>
            <label className="block text-slate-700 mb-1.5" style={{ fontSize: "13px", fontWeight: 600 }}>
              Mật khẩu
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="w-full px-4 py-2.5 rounded-xl border border-slate-200 bg-slate-50 text-slate-900 outline-none focus:border-blue-400 focus:ring-2 focus:ring-blue-100 transition-all"
              style={{ fontSize: "14px" }}
              placeholder="••••••••"
            />
          </div>

          {error && (
            <div className="flex items-center gap-2 px-3 py-2.5 bg-red-50 border border-red-100 rounded-xl">
              <AlertCircle className="w-4 h-4 text-red-500 flex-shrink-0" />
              <p className="text-red-600" style={{ fontSize: "13px" }}>{error}</p>
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 gradient-action text-white rounded-xl transition-all duration-300 hover:-translate-y-0.5 disabled:opacity-60 disabled:translate-y-0 mt-2"
            style={{ fontSize: "14px", fontWeight: 700 }}
          >
            {loading ? "Đang đăng nhập..." : "Đăng nhập"}
          </button>
        </form>
      </div>
    </div>
  );
}
