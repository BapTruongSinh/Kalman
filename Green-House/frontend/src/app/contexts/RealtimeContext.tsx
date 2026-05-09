import { createContext, useContext, useEffect, useMemo, useRef, useState } from "react";
import type {
  AlertItem,
  ControlState,
  DeviceItem,
  GreenhouseMessage,
  GreenhouseStatePacket,
  SensorErrors,
  SensorReading,
} from "../lib/greenhouse.types";

export type DashboardOverview = {
  latest: SensorReading | null;
  control: ControlState;
  device_count: number;
  online_devices: number;
  unread_alerts: number;
  uptime_hint: string;
  recent_alerts: AlertItem[];
  esp32_online: boolean;
};

type RealtimeContextType = {
  overview: DashboardOverview | null;
  latest: SensorReading | null;
  devices: DeviceItem[];
  alerts: AlertItem[];
  chartHistory: SensorReading[];
  sensorErrors: SensorErrors;
  connected: boolean;
  lastUpdated: Date | null;
  sendMode: (mode: "AUTO" | "MANUAL") => void;
  sendDeviceControl: (device: "fan" | "pump" | "light" | "mist", state: "ON" | "OFF") => void;
  markAlertRead: (id: number) => void;
  markAllAlertsRead: () => void;
};

const RealtimeContext = createContext<RealtimeContextType | null>(null);

const WS_URL =
  (import.meta as any).env?.VITE_WS_URL ||
  `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.hostname}:8000/ws/frontend/`;

const MAX_CHART_POINTS = 20;
const RECONNECT_DELAY = 1500;

function formatUptime(updatedAt?: string | null) {
  if (!updatedAt) return "—";
  const diff = Date.now() - new Date(updatedAt).getTime();
  const mins = Math.max(0, Math.floor(diff / 60000));
  if (mins < 1) return "vừa xong";
  if (mins < 60) return `${mins} phút`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs} giờ`;
  return `${Math.floor(hrs / 24)} ngày`;
}

const defaultSensorErrors: SensorErrors = {
  dht: false,
  soil: false,
  light: false,
  gas: false,
};

function makePlaceholderReading(index: number): SensorReading {
  return {
    id: -(index + 1),
    temperature: 0,
    humidity: 0,
    light: 0,
    soil_moisture: 0,
    gas: 0,
    recorded_at: `0-${index + 1}`,
  };
}

function buildInitialChartHistory() {
  return Array.from({ length: MAX_CHART_POINTS }, (_, index) =>
    makePlaceholderReading(index)
  );
}

function isSameReading(a: SensorReading, b: SensorReading) {
  if (a.id != null && b.id != null) {
    return a.id === b.id;
  }
  return a.recorded_at === b.recorded_at;
}

function appendReading(prev: SensorReading[], reading: SensorReading | null) {
  if (!reading) return prev;

  if (prev.length > 0 && isSameReading(prev[prev.length - 1], reading)) {
    return prev;
  }

  return [...prev, reading].slice(-MAX_CHART_POINTS);
}

export function RealtimeProvider({ children }: { children: React.ReactNode }) {
  const socketRef = useRef<WebSocket | null>(null);

  const [overview, setOverview] = useState<DashboardOverview | null>(null);
  const [latest, setLatest] = useState<SensorReading | null>(null);
  const [devices, setDevices] = useState<DeviceItem[]>([]);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [chartHistory, setChartHistory] = useState<SensorReading[]>(() =>
    buildInitialChartHistory()
  );
  const [sensorErrors, setSensorErrors] = useState<SensorErrors>(defaultSensorErrors);
  const [connected, setConnected] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const rebuildOverview = (
    nextLatest: SensorReading | null,
    nextDevices: DeviceItem[],
    nextAlerts: AlertItem[],
    nextControl: ControlState,
    updatedAt: string | null,
    esp32Online: boolean,
  ) => {
    setOverview({
      latest: nextLatest,
      control: nextControl,
      device_count: nextDevices.filter((d) => d.device_type !== "controller").length,
      online_devices: nextDevices.filter(
        (d) => d.device_type !== "controller" && d.status === "online"
      ).length,
      unread_alerts: nextAlerts.filter((a) => !a.is_read).length,
      uptime_hint: formatUptime(updatedAt),
      recent_alerts: nextAlerts.slice(0, 5),
      esp32_online: esp32Online,
    });
  };

  const applyStatePacket = (payload: GreenhouseStatePacket) => {
    const nextLatest = payload.latest ?? null;
    const nextDevices = payload.devices ?? [];
    const nextAlerts = payload.alerts ?? [];
    const nextControl = payload.control;
    const nextSensorErrors = payload.sensor_errors ?? defaultSensorErrors;

    setLatest(nextLatest);
    setDevices(nextDevices);
    setAlerts(nextAlerts);
    setSensorErrors(nextSensorErrors);
    setChartHistory((prev) => appendReading(prev, nextLatest));

    rebuildOverview(
      nextLatest,
      nextDevices,
      nextAlerts,
      nextControl,
      payload.updated_at,
      !!payload.esp32_online,
    );

    setLastUpdated(new Date());
  };

  useEffect(() => {
    let ws: WebSocket | null = null;
    let reconnectTimer: number | null = null;
    let manuallyClosed = false;

    const connect = () => {
      if (
        ws &&
        (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)
      ) {
        return;
      }

      ws = new WebSocket(WS_URL);
      socketRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
      };

      ws.onclose = () => {
        setConnected(false);
        socketRef.current = null;
        ws = null;

        if (!manuallyClosed) {
          if (reconnectTimer) {
            window.clearTimeout(reconnectTimer);
          }

          reconnectTimer = window.setTimeout(() => {
            connect();
          }, RECONNECT_DELAY);
        }
      };

      ws.onerror = () => {
        setConnected(false);
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data) as GreenhouseMessage;
          console.log("Message:", msg);

          if (msg.type === "bootstrap" || msg.type === "state") {
            applyStatePacket(msg.data);
          }
        } catch {
          // ignore invalid message
        }
      };
    };

    connect();

    return () => {
      manuallyClosed = true;

      if (reconnectTimer) {
        window.clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }

      if (ws) {
        ws.onopen = null;
        ws.onclose = null;
        ws.onerror = null;
        ws.onmessage = null;
        ws.close();
      }

      socketRef.current = null;
      ws = null;
    };
  }, []);

  const sendRaw = (payload: unknown) => {
    const ws = socketRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return false;
    ws.send(JSON.stringify(payload));
    return true;
  };

  const value = useMemo<RealtimeContextType>(
    () => ({
      overview,
      latest,
      devices,
      alerts,
      chartHistory,
      sensorErrors,
      connected,
      lastUpdated,
      sendMode: (mode) => {
        sendRaw({ type: "mode", value: mode });
      },
      sendDeviceControl: (device, state) => {
        sendRaw({ type: "device_control", device, state });
      },
      markAlertRead: (id) => {
        setAlerts((prev) => {
          const nextAlerts = prev.map((a) => (a.id === id ? { ...a, is_read: true } : a));
          setOverview((prevOverview) =>
            prevOverview
              ? {
                  ...prevOverview,
                  unread_alerts: nextAlerts.filter((a) => !a.is_read).length,
                  recent_alerts: nextAlerts.slice(0, 5),
                }
              : prevOverview
          );
          return nextAlerts;
        });

        sendRaw({ type: "alert_mark_read", id });
      },
      markAllAlertsRead: () => {
        setAlerts((prev) => {
          const nextAlerts = prev.map((a) => ({ ...a, is_read: true }));
          setOverview((prevOverview) =>
            prevOverview
              ? {
                  ...prevOverview,
                  unread_alerts: 0,
                  recent_alerts: nextAlerts.slice(0, 5),
                }
              : prevOverview
          );
          return nextAlerts;
        });

        sendRaw({ type: "alert_mark_all_read" });
      },
    }),
    [overview, latest, devices, alerts, chartHistory, sensorErrors, connected, lastUpdated]
  );

  return <RealtimeContext.Provider value={value}>{children}</RealtimeContext.Provider>;
}

export function useRealtime() {
  const context = useContext(RealtimeContext);
  if (!context) {
    throw new Error("useRealtime must be used within RealtimeProvider");
  }
  return context;
}