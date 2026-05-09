import { useEffect, useState } from "react";
import {
  ChevronLeft,
  ChevronRight,
  Database,
  Clock3,
  Thermometer,
  Droplets,
  Sun,
  Sprout,
  Calendar,
  Download,
} from "lucide-react";
import { apiClient } from "../api/client";
import type { SensorReading } from "../api/endpoints";

interface SensorHistoryResponse {
  items: SensorReading[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

type QuickFilter = "today" | "7days" | "30days" | "all" | "custom";

function formatMetric(value: number | null, unit: string) {
  if (value === null || value === undefined) return "--";
  return `${Number(value).toFixed(1)} ${unit}`;
}

function toIsoOrEmpty(value: string) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toISOString();
}

function toLocalInputValue(date: Date) {
  const offset = date.getTimezoneOffset();
  const local = new Date(date.getTime() - offset * 60_000);
  return local.toISOString().slice(0, 16);
}

function getQuickFilterRange(filter: Exclude<QuickFilter, "custom">) {
  const now = new Date();

  switch (filter) {
    case "today": {
      const start = new Date(now.getFullYear(), now.getMonth(), now.getDate());
      return {
        from: toLocalInputValue(start),
        to: toLocalInputValue(now),
      };
    }
    case "7days": {
      const start = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
      return {
        from: toLocalInputValue(start),
        to: toLocalInputValue(now),
      };
    }
    case "30days": {
      const start = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
      return {
        from: toLocalInputValue(start),
        to: toLocalInputValue(now),
      };
    }
    case "all":
      return {
        from: "",
        to: "",
      };
  }
}

function getStatusColor(
  value: number | null | undefined,
  type: "temperature" | "humidity" | "light" | "soilMoisture"
) {
  if (value === null || value === undefined) return "text-slate-500";

  if (type === "temperature") {
    if (value < 20 || value > 32) return "text-red-600";
    if (value < 22 || value > 30) return "text-yellow-600";
    return "text-green-600";
  }

  if (type === "humidity") {
    if (value < 50 || value > 80) return "text-red-600";
    if (value < 55 || value > 75) return "text-yellow-600";
    return "text-green-600";
  }

  if (type === "light") {
    if (value < 20 || value > 90) return "text-yellow-600";
    return "text-green-600";
  }

  if (type === "soilMoisture") {
    if (value < 55 || value > 75) return "text-red-600";
    if (value < 60 || value > 72) return "text-yellow-600";
    return "text-green-600";
  }

  return "text-slate-600";
}

async function fetchSensorHistory(params: {
  page: number;
  pageSize: number;
  dateFrom?: string;
  dateTo?: string;
}) {
  const search = new URLSearchParams({
    page: String(params.page),
    page_size: String(params.pageSize),
  });

  if (params.dateFrom) {
    search.set("date_from", params.dateFrom);
  }

  if (params.dateTo) {
    search.set("date_to", params.dateTo);
  }

  return apiClient.get<SensorHistoryResponse>(
    `/sensor-readings/history/?${search.toString()}`
  );
}

export function SensorHistory() {
  const [rows, setRows] = useState<SensorReading[]>([]);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [quickFilter, setQuickFilter] = useState<QuickFilter>("custom");
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [pageLoading, setPageLoading] = useState(false);
  const [error, setError] = useState("");

  const invalidRange =
    !!dateFrom && !!dateTo && new Date(dateFrom).getTime() > new Date(dateTo).getTime();

  const loadData = async (
    nextPage = page,
    nextDateFrom = dateFrom,
    nextDateTo = dateTo
  ) => {
    const isFirstLoad = rows.length === 0 && nextPage === 1;

    try {
      setError("");

      if (isFirstLoad) {
        setLoading(true);
      } else {
        setPageLoading(true);
      }

      const res = await fetchSensorHistory({
        page: nextPage,
        pageSize,
        dateFrom: toIsoOrEmpty(nextDateFrom) || undefined,
        dateTo: toIsoOrEmpty(nextDateTo) || undefined,
      });

      const data = res.data;
      setRows(data.items ?? []);
      setPage(data.page ?? 1);
      setTotalPages(Math.max(data.total_pages ?? 1, 1));
    } catch {
      setError("Không tải được lịch sử cảm biến.");
      if (isFirstLoad) {
        setRows([]);
        setTotalPages(1);
      }
    } finally {
      setLoading(false);
      setPageLoading(false);
    }
  };

  useEffect(() => {
    if (invalidRange) return;
    void loadData(page, dateFrom, dateTo);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, dateFrom, dateTo]);

  const handlePrev = () => {
    if (page > 1 && !pageLoading) {
      setPage((prev) => prev - 1);
    }
  };

  const handleNext = () => {
    if (page < totalPages && !pageLoading) {
      setPage((prev) => prev + 1);
    }
  };

  const applyQuickFilter = (filter: Exclude<QuickFilter, "custom">) => {
    const range = getQuickFilterRange(filter);
    setQuickFilter(filter);
    setPage(1);
    setDateFrom(range.from);
    setDateTo(range.to);
  };

  const handleExportCsv = async () => {
    try {
      const allRows: SensorReading[] = [];
      let currentPage = 1;
      let lastPage = 1;

      do {
        const res = await fetchSensorHistory({
          page: currentPage,
          pageSize: 500,
          dateFrom: toIsoOrEmpty(dateFrom) || undefined,
          dateTo: toIsoOrEmpty(dateTo) || undefined,
        });

        const data = res.data;
        allRows.push(...(data.items ?? []));
        lastPage = Math.max(data.total_pages ?? 1, 1);
        currentPage += 1;
      } while (currentPage <= lastPage);

      if (!allRows.length) return;

      const csvContent = [
        ["Thời gian", "Nhiệt độ (°C)", "Độ ẩm KK (%)", "Ánh sáng (%)", "Độ ẩm đất (%)"],
        ...allRows.map((row) => [
          row.recorded_at ? new Date(row.recorded_at).toLocaleString("vi-VN") : "--",
          row.temperature != null ? Number(row.temperature).toFixed(1) : "",
          row.humidity != null ? Number(row.humidity).toFixed(1) : "",
          row.light != null ? Number(row.light).toFixed(1) : "",
          row.soil_moisture != null ? Number(row.soil_moisture).toFixed(1) : "",
        ]),
      ]
        .map((row) => row.join(","))
        .join("\n");

      const blob = new Blob(["\uFEFF" + csvContent], {
        type: "text/csv;charset=utf-8;",
      });

      const link = document.createElement("a");
      const url = URL.createObjectURL(blob);
      link.href = url;

      const dateLabel =
        dateFrom || dateTo
          ? `tu-${dateFrom || "dau"}_den-${dateTo || "nay"}`
          : "tat-ca";

      link.download = `lich-su-cam-bien-${dateLabel}.csv`;
      link.click();

      URL.revokeObjectURL(url);
    } catch {
      setError("Không xuất được file CSV.");
    }
  };

  return (
    <div className="space-y-5">
      <div className="elevated-card rounded-3xl p-5">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
          <div className="flex flex-wrap gap-3">
            {[
              { id: "today", label: "Hôm nay" },
              { id: "7days", label: "7 ngày" },
              { id: "30days", label: "30 ngày" },
              { id: "all", label: "Tất cả" },
            ].map((item) => {
              const active = quickFilter === item.id;

              return (
                <button
                  key={item.id}
                  onClick={() => applyQuickFilter(item.id as Exclude<QuickFilter, "custom">)}
                  className={`inline-flex items-center gap-2 rounded-2xl px-5 py-3 transition-all ${active
                      ? "bg-blue-600 text-white shadow-sm"
                      : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                    }`}
                  style={{ fontSize: "13px", fontWeight: 700 }}
                >
                  <Calendar className="w-4 h-4" />
                  {item.label}
                </button>
              );
            })}
          </div>

          <button
            onClick={handleExportCsv}
            disabled={!rows.length}
            className="inline-flex items-center gap-2 rounded-2xl bg-blue-600 px-5 py-3 text-white shadow-sm transition-all hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
            style={{ fontSize: "13px", fontWeight: 700 }}
          >
            <Download className="w-4 h-4" />
            Xuất CSV
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <label
              className="block text-slate-500 mb-2"
              style={{ fontSize: "11px", fontWeight: 700 }}
            >
              Từ ngày giờ
            </label>
            <input
              type="datetime-local"
              value={dateFrom}
              onChange={(e) => {
                setQuickFilter("custom");
                setPage(1);
                setDateFrom(e.target.value);
              }}
              className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 outline-none"
              style={{ fontSize: "13px", fontWeight: 600 }}
            />
          </div>

          <div>
            <label
              className="block text-slate-500 mb-2"
              style={{ fontSize: "11px", fontWeight: 700 }}
            >
              Đến ngày giờ
            </label>
            <input
              type="datetime-local"
              value={dateTo}
              onChange={(e) => {
                setQuickFilter("custom");
                setPage(1);
                setDateTo(e.target.value);
              }}
              className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 outline-none"
              style={{ fontSize: "13px", fontWeight: 600 }}
            />
          </div>
        </div>

        {invalidRange && (
          <div
            className="mt-3 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-red-600"
            style={{ fontSize: "12px", fontWeight: 600 }}
          >
            Thời gian bắt đầu không được lớn hơn thời gian kết thúc.
          </div>
        )}
      </div>

      <div className="elevated-card rounded-3xl overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-200">
          <h4 className="text-slate-900" style={{ fontSize: "15px", fontWeight: 700 }}>
            Bảng dữ liệu đo
          </h4>
        </div>

        {loading ? (
          <div className="p-10 text-center text-slate-400" style={{ fontSize: "13px" }}>
            Đang tải lịch sử cảm biến...
          </div>
        ) : error ? (
          <div
            className="p-10 text-center text-red-500"
            style={{ fontSize: "13px", fontWeight: 600 }}
          >
            {error}
          </div>
        ) : rows.length === 0 ? (
          <div className="p-10 text-center">
            <div className="w-16 h-16 bg-slate-50 rounded-2xl flex items-center justify-center mx-auto mb-3 border border-slate-200">
              <Database className="w-7 h-7 text-slate-400" />
            </div>
            <p className="text-slate-700" style={{ fontSize: "15px", fontWeight: 700 }}>
              Chưa có lịch sử đo
            </p>
            <p className="text-slate-500 mt-1" style={{ fontSize: "13px" }}>
              Khi ESP gửi dữ liệu cảm biến, bản ghi sẽ xuất hiện ở đây
            </p>
          </div>
        ) : (
          <div
            className={`overflow-x-auto transition-opacity duration-200 ${pageLoading ? "opacity-60" : "opacity-100"
              }`}
          >
            <table className="w-full min-w-[760px]">
              <thead>
                <tr className="bg-gradient-to-r from-blue-50 to-blue-100 border-b border-slate-200">
                  <th
                    className="text-left px-5 py-4 text-slate-700"
                    style={{ fontSize: "12px", fontWeight: 700 }}
                  >
                    <div className="flex items-center gap-2">
                      <Clock3 className="w-4 h-4 text-blue-600" />
                      Thời gian
                    </div>
                  </th>
                  <th
                    className="text-center px-5 py-4 text-slate-700"
                    style={{ fontSize: "12px", fontWeight: 700 }}
                  >
                    <div className="flex items-center justify-center gap-2">
                      <Thermometer className="w-4 h-4 text-orange-600" />
                      Nhiệt độ
                    </div>
                  </th>
                  <th
                    className="text-center px-5 py-4 text-slate-700"
                    style={{ fontSize: "12px", fontWeight: 700 }}
                  >
                    <div className="flex items-center justify-center gap-2">
                      <Droplets className="w-4 h-4 text-cyan-600" />
                      Độ ẩm KK
                    </div>
                  </th>
                  <th
                    className="text-center px-5 py-4 text-slate-700"
                    style={{ fontSize: "12px", fontWeight: 700 }}
                  >
                    <div className="flex items-center justify-center gap-2">
                      <Sun className="w-4 h-4 text-yellow-600" />
                      Ánh sáng
                    </div>
                  </th>
                  <th
                    className="text-center px-5 py-4 text-slate-700"
                    style={{ fontSize: "12px", fontWeight: 700 }}
                  >
                    <div className="flex items-center justify-center gap-2">
                      <Sprout className="w-4 h-4 text-green-600" />
                      Độ ẩm đất
                    </div>
                  </th>
                </tr>
              </thead>

              <tbody>
                {rows.map((row, index) => {
                  const recordedAt = new Date(row.recorded_at);

                  return (
                    <tr
                      key={row.id}
                      className={`border-b border-slate-100 hover:bg-blue-50/30 transition-colors ${index % 2 === 0 ? "bg-white" : "bg-slate-50/50"
                        }`}
                    >
                      <td className="px-5 py-4">
                        <div>
                          <p
                            className="text-slate-800"
                            style={{ fontSize: "13px", fontWeight: 600 }}
                          >
                            {Number.isNaN(recordedAt.getTime())
                              ? "--"
                              : recordedAt.toLocaleDateString("vi-VN")}
                          </p>
                          <p className="text-slate-400" style={{ fontSize: "11px" }}>
                            {Number.isNaN(recordedAt.getTime())
                              ? "--"
                              : recordedAt.toLocaleTimeString("vi-VN", {
                                hour: "2-digit",
                                minute: "2-digit",
                                second: "2-digit",
                              })}
                          </p>
                        </div>
                      </td>

                      <td className="px-5 py-4 text-center">
                        <span
                          className={`font-semibold ${getStatusColor(
                            row.temperature,
                            "temperature"
                          )}`}
                          style={{ fontSize: "14px" }}
                        >
                          {formatMetric(row.temperature, "°C")}
                        </span>
                      </td>

                      <td className="px-5 py-4 text-center">
                        <span
                          className={`font-semibold ${getStatusColor(
                            row.humidity,
                            "humidity"
                          )}`}
                          style={{ fontSize: "14px" }}
                        >
                          {formatMetric(row.humidity, "%")}
                        </span>
                      </td>

                      <td className="px-5 py-4 text-center">
                        <span
                          className={`font-semibold ${getStatusColor(row.light, "light")}`}
                          style={{ fontSize: "14px" }}
                        >
                          {formatMetric(row.light, "%")}
                        </span>
                      </td>

                      <td className="px-5 py-4 text-center">
                        <span
                          className={`font-semibold ${getStatusColor(
                            row.soil_moisture,
                            "soilMoisture"
                          )}`}
                          style={{ fontSize: "14px" }}
                        >
                          {formatMetric(row.soil_moisture, "%")}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        <div className="px-5 py-4 border-t border-slate-200 flex items-center justify-between">
          <button
            onClick={handlePrev}
            disabled={page <= 1 || invalidRange || pageLoading}
            className="px-3 py-2 rounded-xl border border-slate-200 bg-white text-slate-700 disabled:opacity-50 disabled:cursor-not-allowed hover:bg-slate-50 flex items-center gap-2"
            style={{ fontSize: "13px", fontWeight: 600 }}
          >
            <ChevronLeft className="w-4 h-4" />
            Trước
          </button>

          <div className="text-slate-600" style={{ fontSize: "13px", fontWeight: 600 }}>
            Trang {page} / {totalPages}
          </div>

          <button
            onClick={handleNext}
            disabled={page >= totalPages || invalidRange || pageLoading}
            className="px-3 py-2 rounded-xl border border-slate-200 bg-white text-slate-700 disabled:opacity-50 disabled:cursor-not-allowed hover:bg-slate-50 flex items-center gap-2"
            style={{ fontSize: "13px", fontWeight: 600 }}
          >
            Sau
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}