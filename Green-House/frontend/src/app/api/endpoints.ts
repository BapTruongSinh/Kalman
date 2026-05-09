import { apiClient } from "./client";

// ─── Auth ───────────────────────────────────────────────────────────────────
export interface LoginResponse {
  access: string;
  refresh: string;
}
export const authLogin = (username: string, password: string) =>
  apiClient.post<LoginResponse>("/auth/login/", { username, password });

// ─── Control ────────────────────────────────────────────────────────────────
export interface ControlState {
  mode: "AUTO" | "MANUAL";
  manual_reason: string;
  manual_changed_at: string | null;
  updated_at: string;
}
export const getControlState = () =>
  apiClient.get<ControlState>("/control/state/");
export const setControlMode = (mode: "AUTO" | "MANUAL", reason = "") =>
  apiClient.post<ControlState>("/control/mode/", { mode, reason });

export interface ControlProfile {
  crop_name: string;
  crop_kc: number;
  target_low: number;
  target_high: number;
  step_seconds: number;
  horizon_steps: number;
  pump_min_seconds: number;
  pump_max_seconds: number;
  pump_grid_seconds: number;
  soft_daily_pump_cap_seconds: number;
  weight_band: number;
  weight_water: number;
  weight_switch: number;
  weight_daily: number;
  weight_terminal: number;
  adaptive_enabled: boolean;
  adaptive_bias_window: number;
  adaptive_max_abs_bias: number;
  stale_after_seconds: number;
  actuator_enabled: boolean;
  updated_at: string;
}

export const getAutoSettings = () =>
  apiClient.get<ControlProfile>("/auto-settings/");
export const updateAutoSettings = (payload: Partial<ControlProfile>) =>
  apiClient.patch<ControlProfile>("/auto-settings/", payload);

export interface EstimationCycle {
  id?: number;
  greenhouse_id?: number;
  sensor_data?: number;
  sample_ts: string;
  cycle_index: number;
  slice_type?: string;
  validation_status: string;
  validation_reason?: string;
  preprocess_status: string;
  cycle_status: string;
  adaptive_status: string;
  raw_soil_moisture: number | null;
  arx_predicted: number | null;
  kf_x_posterior: number | null;
  kf_innovation?: number | null;
  kf_R: number | null;
  kf_K?: number | null;
  latency_ms: number | null;
  error_message?: string;
}

export interface RunItem {
  id: number;
  name: string;
  run_type: string;
  status: string;
  greenhouse_id: number | null;
  greenhouse_name: string;
  created_at: string;
}

export const getRuns = () => apiClient.get<RunItem[]>("/runs/");
export const getRunSeries = (runId: number, limit = 500) =>
  apiClient.get<EstimationCycle[]>(`/runs/${runId}/series/?limit=${limit}`);

export interface KalmanTestSeriesResponse {
  source_database: string;
  source_table: string;
  limit: number;
  total_selected: number;
  points: EstimationCycle[];
}

export const getKalmanTestSeries = (limit = 100000) =>
  apiClient.get<KalmanTestSeriesResponse>(`/kalman-test/series/?limit=${limit}`);

export interface MPCTestPoint {
  timestamp: string;
  actual_soil_moisture: number | null;
  mpc_soil_moisture: number | null;
  rule_based_soil_moisture: number | null;
  mpc_pump_seconds: number | null;
  rule_based_pump_seconds: number | null;
  target_low: number;
  target_high: number;
  safety_status: string;
  reason: string;
}

export interface MPCTestSeriesResponse {
  greenhouse_id: number;
  source_table: string;
  total_selected: number;
  points: MPCTestPoint[];
}

export const getMPCTestSeries = () =>
  apiClient.get<MPCTestSeriesResponse>("/mpc-test/series/");

export interface AMPCRecommendation {
  id: number;
  sensor_data: number | null;
  estimation: number | null;
  device_command: number | null;
  mode: "AUTO" | "MANUAL";
  pump_seconds: number;
  step_seconds: number;
  predicted_soil_moisture: number[];
  target_band: { low?: number; high?: number };
  objective_cost: number;
  safety_status: string;
  reason: string;
  bias_correction: number;
  bias_window_count: number;
  used_today_pump_seconds: number;
  command_created: boolean;
  actuator_status: string;
  created_at: string;
}

export interface AMPCSchedulerState {
  greenhouse_id: number | null;
  is_enabled: boolean;
  interval_seconds: number;
  is_executing: boolean;
  last_started_at: string | null;
  last_stopped_at: string | null;
  last_run_at: string | null;
  next_run_at: string | null;
  last_status: string;
  last_error: string;
  updated_at: string;
}

export interface ForecastResponse {
  latest: SensorReading | null;
  estimation: EstimationCycle | null;
  recommendation: AMPCRecommendation | null;
  scheduler: AMPCSchedulerState;
  history: SensorReading[];
}

export const getForecast = () => apiClient.get<ForecastResponse>("/forecast/");
export const runAutoRecommendation = () =>
  apiClient.post<AMPCRecommendation>("/control/auto-recommendation/");
export const getAmpcScheduler = () =>
  apiClient.get<AMPCSchedulerState>("/control/ampc-scheduler/");
export const startAmpcScheduler = () =>
  apiClient.post<AMPCSchedulerState>("/control/ampc-scheduler/start/");
export const stopAmpcScheduler = () =>
  apiClient.post<AMPCSchedulerState>("/control/ampc-scheduler/stop/");

// ─── Dashboard ───────────────────────────────────────────────────────────────
export interface DashboardOverview {
  latest: SensorReading | null;
  control: ControlState;
  device_count: number;
  online_devices: number;
  unread_alerts: number;
  uptime_hint: string;
  recent_alerts: AlertItem[];
  esp32_online: boolean;
}
export const getDashboardOverview = () =>
  apiClient.get<DashboardOverview>("/dashboard/overview/");

// ─── Sensor Readings ─────────────────────────────────────────────────────────
export interface SensorReading {
  id: number;
  temperature: number | null;
  humidity: number | null;
  light: number | null;
  soil_moisture: number | null;
  recorded_at: string;
}

export const getLatestReading = () =>
  apiClient.get<SensorReading>("/sensor-readings/latest/");

export type ChartMetric = "temperature" | "humidity" | "light" | "soil_moisture";

export interface ChartPoint {
  recorded_at: string;
  value: number;
}

export interface ChartResponse {
  metric: ChartMetric;
  points: ChartPoint[];
}

export const getChartData = (metric: ChartMetric, hours: number) =>
  apiClient.get<ChartResponse>(`/sensor-readings/chart/?metric=${metric}&hours=${hours}`);

export interface SensorHistoryResponse {
  items: SensorReading[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

export interface SensorHistoryParams {
  page?: number;
  pageSize?: number;
  hours?: number;
  dateFrom?: string;
  dateTo?: string;
}

export const getSensorHistory = ({
  page = 1,
  pageSize = 20,
  hours,
  dateFrom,
  dateTo,
}: SensorHistoryParams = {}) => {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });

  if (dateFrom) {
    params.set("date_from", dateFrom);
  }

  if (dateTo) {
    params.set("date_to", dateTo);
  }

  if (!dateFrom && !dateTo && hours && hours > 0) {
    params.set("hours", String(hours));
  }

  return apiClient.get<SensorHistoryResponse>(`/sensor-readings/history/?${params.toString()}`);
};

// ─── Devices ─────────────────────────────────────────────────────────────────
export interface DeviceItem {
  id: number;
  name: string;
  code: string;
  uid?: string;
  device_type: "controller" | "fan" | "pump" | "light";
  status: "online" | "offline" | "error";
  is_enabled: boolean;
  state?: {
    is_on: boolean;
    desired_on: boolean;
    last_command: string;
    last_value: string;
  };
}
export const getDevices = () => apiClient.get<DeviceItem[]>("/devices/");
export const toggleDevice = (pk: number) =>
  apiClient.post<DeviceItem>(`/devices/${pk}/toggle/`);
export const sendDeviceCommand = (pk: number, command: string, value: string) =>
  apiClient.post(`/devices/${pk}/command/`, { command, value });

// ─── Alerts ──────────────────────────────────────────────────────────────────
export interface AlertItem {
  id: number;
  level: "info" | "warning" | "error" | "success";
  title: string;
  message: string;
  is_read: boolean;
  happened_at: string;
}
export const getAlerts = () => apiClient.get<AlertItem[]>("/alerts/");
export const markAlertRead = (pk: number) =>
  apiClient.post<AlertItem>(`/alerts/${pk}/mark_read/`);
export const markAllAlertsRead = () =>
  apiClient.post<{ updated: number }>("/alerts/mark_all_read/");
