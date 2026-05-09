import { useMemo, useState } from "react";
import { Fan, Lightbulb, Droplets, Power, Activity, Zap, Loader2, CloudRain } from "lucide-react";
import type { ControlState, DeviceItem } from "../lib/greenhouse.types";
import { useRealtime } from "../contexts/RealtimeContext";

const DEVICE_META: Record<
  "fan" | "light" | "pump" | "mist",
  {
    label: string;
    description: string;
    icon: React.ElementType;
    iconColor: string;
    iconBg: string;
    power: number;
    activeClass: string;
    activeGlowClass: string;
    activeProgressClass: string;
  }
> = {
  fan: {
    label: "Quạt thông gió",
    description: "Điều hòa nhiệt độ",
    icon: Fan,
    iconColor: "text-blue-500",
    iconBg: "bg-blue-50",
    power: 0,
    activeClass: "device-icon-fan",
    activeGlowClass: "device-glow-fan",
    activeProgressClass: "bg-blue-500",
  },
  light: {
    label: "Đèn chiếu sáng",
    description: "Bổ sung ánh sáng",
    icon: Lightbulb,
    iconColor: "text-amber-500",
    iconBg: "bg-amber-50",
    power: 0,
    activeClass: "device-icon-light",
    activeGlowClass: "device-glow-light",
    activeProgressClass: "bg-amber-500",
  },
  pump: {
    label: "Bơm tưới nước",
    description: "Hệ thống tưới nhỏ giọt",
    icon: Droplets,
    iconColor: "text-violet-500",
    iconBg: "bg-violet-50",
    power: 0,
    activeClass: "device-icon-pump",
    activeGlowClass: "device-glow-pump",
    activeProgressClass: "bg-violet-500",
  },
  mist: {
    label: "Máy phun sương",
    description: "Tăng độ ẩm không khí",
    icon: CloudRain,
    iconColor: "text-teal-500",
    iconBg: "bg-teal-50",
    power: 0,
    activeClass: "device-icon-mist",
    activeGlowClass: "device-glow-mist",
    activeProgressClass: "bg-teal-500",
  },
};

type DeviceType = "fan" | "light" | "pump" | "mist";

type ViewDevice = {
  id: number;
  name: string;
  code: string;
  device_type: DeviceType;
  status: "online" | "offline";
  state: {
    is_on: boolean;
    updated_at?: string;
  } | null;
};

const DEFAULT_DEVICES: ViewDevice[] = [
  {
    id: 1,
    name: "Quạt thông gió",
    code: "fan-1",
    device_type: "fan",
    status: "offline",
    state: { is_on: false },
  },
  {
    id: 2,
    name: "Đèn chiếu sáng",
    code: "light-1",
    device_type: "light",
    status: "offline",
    state: { is_on: false },
  },
  {
    id: 3,
    name: "Bơm tưới nước",
    code: "pump-1",
    device_type: "pump",
    status: "offline",
    state: { is_on: false },
  },
  {
    id: 4,
    name: "Máy phun sương",
    code: "mist-1",
    device_type: "mist",
    status: "offline",
    state: { is_on: false },
  },
];

function normalizeDevices(devices: DeviceItem[]): ViewDevice[] {
  const picked = new Map<DeviceType, ViewDevice>();

  for (const device of devices) {
    if (device.device_type !== "fan" && device.device_type !== "light" && device.device_type !== "pump" && device.device_type !== "mist") {
      continue;
    }

    picked.set(device.device_type, {
      id: device.id,
      name: device.name,
      code: device.code,
      device_type: device.device_type,
      status: device.status,
      state: device.state,
    });
  }

  return DEFAULT_DEVICES.map((fallback) => picked.get(fallback.device_type) ?? fallback);
}

interface DeviceControlProps {
  control: ControlState | null;
}

export function DeviceControl({ control }: DeviceControlProps) {
  const { devices, sensorErrors, sendMode, sendDeviceControl } = useRealtime();
  const [togglingKey, setTogglingKey] = useState<DeviceType | null>(null);
  const [switchingAuto, setSwitchingAuto] = useState(false);

  const visibleDevices = useMemo(() => normalizeDevices(devices), [devices]);
  const isAuto = control?.mode === "AUTO";
  const isAutoLocked = !!sensorErrors?.dht;

  const handleToggleAuto = async () => {
    if (!isAuto && isAutoLocked) return;

    setSwitchingAuto(true);
    sendMode(isAuto ? "MANUAL" : "AUTO");
    setTimeout(() => setSwitchingAuto(false), 500);
  };

  const handleToggle = async (deviceType: DeviceType, isOn: boolean) => {
    if (isAuto) return;
    setTogglingKey(deviceType);
    sendDeviceControl(deviceType, isOn ? "OFF" : "ON");
    setTimeout(() => setTogglingKey(null), 100);
  };

  const handleAllDevices = async (turnOn: boolean) => {
    if (isAuto) return;
    (["fan", "pump", "light", "mist"] as DeviceType[]).forEach((device) => {
      sendDeviceControl(device, turnOn ? "ON" : "OFF");
    });
  };

  const activeCount = visibleDevices.filter((d) => d.state?.is_on).length;
  const onlineCount = visibleDevices.filter((d) => d.status === "online").length;

  return (
    <div className="elevated-card rounded-3xl overflow-hidden">
      <div className="px-5 py-4 border-b border-slate-200 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 bg-blue-50 rounded-xl flex items-center justify-center border border-blue-100">
            <Zap className="w-4 h-4 text-blue-600" />
          </div>
          <div>
            <h3 className="text-slate-900">Điều khiển thiết bị</h3>
            <p className="text-slate-400" style={{ fontSize: "11px" }}>
              {isAuto ? "Đang bật chế độ tự động" : "Đang ở chế độ thủ công"}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleToggleAuto}
            disabled={switchingAuto || (!isAuto && isAutoLocked)}
            className={`px-3 py-2 rounded-xl transition-all duration-300 disabled:opacity-60 disabled:cursor-not-allowed flex items-center gap-2 ${isAuto
                ? "bg-blue-600 text-white hover:bg-blue-700"
                : "bg-slate-100 text-slate-700 border border-slate-200 hover:bg-slate-200"
              }`}
            style={{ fontSize: "12px", fontWeight: 700 }}
          >
            {switchingAuto ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Power className="w-3.5 h-3.5" />}
            {isAuto ? "Tắt tự động" : "Bật tự động"}
          </button>
        </div>
      </div>

      <div className="p-5 space-y-3">
        {isAuto && (
          <div
            className="rounded-xl border border-blue-100 bg-blue-50 px-3 py-2 text-blue-700"
            style={{ fontSize: "12px" }}
          >
            Chế độ tự động đang bật.
          </div>
        )}

        {visibleDevices.map((device) => {
          const meta = DEVICE_META[device.device_type];
          const Icon = meta.icon;
          const isOn = device.state?.is_on ?? false;
          const isToggling = togglingKey === device.device_type;

          return (
            <div
              key={device.device_type}
              className={`flex items-center gap-4 p-4 rounded-2xl border transition-all duration-300 ${isOn ? "border-blue-100 bg-blue-50/50 shadow-[0_8px_20px_rgba(59,130,246,0.08)]" : "border-slate-200 bg-slate-50/60"
                } ${isAuto ? "opacity-70" : ""}`}
            >
              <div className="relative w-11 h-11 flex items-center justify-center flex-shrink-0">
                {isOn && <span className={`absolute inset-0 rounded-xl ${meta.activeGlowClass}`}></span>}

                <div
                  className={`relative w-11 h-11 rounded-xl flex items-center justify-center transition-all border ${isOn ? `${meta.iconBg} border-white` : "bg-white border-slate-200"
                    }`}
                >
                  <Icon
                    className={`w-5 h-5 transition-all duration-300 ${isOn ? `${meta.iconColor} ${meta.activeClass}` : "text-slate-400"
                      }`}
                  />
                </div>
              </div>

              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <p
                    className={`${isOn ? "text-slate-900" : "text-slate-500"}`}
                    style={{ fontSize: "14px", fontWeight: 600 }}
                  >
                    {meta.label}
                  </p>
                </div>

                <p className="text-slate-400" style={{ fontSize: "12px" }}>
                  {meta.description}
                </p>
              </div>

              <div className="flex flex-col items-end gap-2">
                <span
                  className={`px-2 py-0.5 rounded-full text-xs font-medium ${isOn ? "bg-blue-100 text-blue-700" : "bg-slate-200 text-slate-600"
                    }`}
                  style={{ fontSize: "11px" }}
                >
                  {isOn ? "Bật" : "Tắt"}
                </span>

                <button
                  onClick={() => handleToggle(device.device_type, isOn)}
                  disabled={isAuto || isToggling}
                  className={`relative w-12 h-6 rounded-full transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed ${isOn ? "bg-blue-600" : "bg-slate-300"
                    }`}
                >
                  {isToggling ? (
                    <Loader2 className="w-3.5 h-3.5 text-white absolute top-1 left-3.5 animate-spin" />
                  ) : (
                    <span
                      className={`absolute top-0.5 w-5 h-5 bg-white rounded-full shadow-sm transition-all duration-300 ${isOn ? "left-6" : "left-0.5"
                        }`}
                    ></span>
                  )}
                </button>
              </div>
            </div>
          );
        })}
      </div>

      <div className="px-5 pb-5 flex gap-3">
        <button
          onClick={() => handleAllDevices(true)}
          disabled={isAuto}
          className="flex-1 py-2 gradient-action text-white rounded-xl transition-all duration-300 hover:-translate-y-0.5 flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
          style={{ fontSize: "13px", fontWeight: 600 }}
        >
          <Power className="w-3.5 h-3.5" /> Bật tất cả
        </button>

        <button
          onClick={() => handleAllDevices(false)}
          disabled={isAuto}
          className="flex-1 py-2 bg-slate-100 text-slate-700 rounded-xl border border-slate-200 transition-colors hover:bg-slate-200 flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
          style={{ fontSize: "13px", fontWeight: 600 }}
        >
          <Power className="w-3.5 h-3.5" /> Tắt tất cả
        </button>
      </div>
    </div>
  );
}