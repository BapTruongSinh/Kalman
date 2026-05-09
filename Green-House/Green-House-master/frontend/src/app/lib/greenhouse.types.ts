export type SensorReading = {
  id: number;
  temperature: number | null;
  humidity: number | null;
  light: number | null;
  soil_moisture: number | null;
  gas: number | null;
  payload?: Record<string, unknown>;
  recorded_at: string;
};

export type ControlState = {
  mode: "AUTO" | "MANUAL";
  manual_reason: string;
  manual_changed_at: string | null;
  updated_at: string;
};

export type DeviceItem = {
  id: number;
  name: string;
  code: string;
  device_type: "fan" | "pump" | "light" | "controller" | "mist";
  status: "online" | "offline";
  state: {
    is_on: boolean;
    updated_at?: string;
  } | null;
};

export type AlertItem = {
  id: number;
  title: string;
  message: string;
  level: "info" | "warning" | "error" | "success";
  is_read: boolean;
  happened_at: string;
};

export type SensorErrors = {
  dht: boolean;
  soil: boolean;
  light: boolean;
  gas: boolean;
};

export type GreenhouseStatePacket = {
  latest: SensorReading | null;
  control: ControlState;
  devices: DeviceItem[];
  alerts: AlertItem[];
  sensor_errors: SensorErrors;
  esp32_online: boolean;
  updated_at: string | null;
};

export type GreenhouseMessage =
  | { type: "bootstrap"; data: GreenhouseStatePacket }
  | { type: "state"; data: GreenhouseStatePacket }
  | { type: "error"; data?: unknown; reason?: string };