import { useEffect, useState } from "react";
import { Save, Zap } from "lucide-react";
import {
  ControlProfile,
  getAutoSettings,
  runAutoRecommendation,
  updateAutoSettings,
} from "../api/endpoints";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Switch } from "./ui/switch";

type NumericField = keyof Pick<
  ControlProfile,
  | "crop_kc"
  | "target_low"
  | "target_high"
  | "pump_max_seconds"
  | "soft_daily_pump_cap_seconds"
  | "weight_band"
  | "weight_water"
  | "weight_switch"
  | "weight_daily"
  | "weight_terminal"
>;

function toNumber(value: string) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : 0;
}

export function AutoSettings() {
  const [profile, setProfile] = useState<ControlProfile | null>(null);
  const [saving, setSaving] = useState(false);
  const [running, setRunning] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    getAutoSettings()
      .then((response) => setProfile(response.data))
      .catch(() => setMessage("Khong tai duoc cau hinh AUTO."));
  }, []);

  const updateNumber = (field: NumericField, value: string) => {
    setProfile((current) => current ? { ...current, [field]: toNumber(value) } : current);
  };

  const save = async () => {
    if (!profile) return;
    setSaving(true);
    setMessage("");
    try {
      const response = await updateAutoSettings(profile);
      setProfile(response.data);
      setMessage("Da luu cau hinh AUTO.");
    } catch {
      setMessage("Luu cau hinh that bai.");
    } finally {
      setSaving(false);
    }
  };

  const run = async () => {
    setRunning(true);
    setMessage("");
    try {
      const response = await runAutoRecommendation();
      setMessage(`AMPC: ${response.data.safety_status} - bom ${response.data.pump_seconds}s`);
    } catch {
      setMessage("Chay AMPC that bai.");
    } finally {
      setRunning(false);
    }
  };

  if (!profile) {
    return (
      <div className="elevated-card rounded-3xl p-5">
        <p className="text-slate-500" style={{ fontSize: "13px" }}>Dang tai cau hinh AUTO...</p>
      </div>
    );
  }

  const fields: Array<[NumericField, string, string]> = [
    ["target_low", "Nguong am thap", "%"],
    ["target_high", "Nguong am cao", "%"],
    ["pump_max_seconds", "Bom toi da moi buoc", "giay"],
    ["soft_daily_pump_cap_seconds", "Gioi han bom/ngay", "giay"],
    ["weight_band", "w_band", ""],
    ["weight_water", "w_water", ""],
    ["weight_switch", "w_switch", ""],
    ["weight_daily", "w_daily", ""],
    ["weight_terminal", "w_terminal", ""],
    ["crop_kc", "He so cay trong Kc", ""],
  ];

  return (
    <div className="elevated-card rounded-3xl p-5">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <div>
          <p className="text-slate-800" style={{ fontSize: "15px", fontWeight: 800 }}>
            Cau hinh AMPC
          </p>
          <p className="text-slate-500" style={{ fontSize: "12px" }}>
            Cac tham so cay trong va trong so dieu khien dang luu tren backend.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button onClick={run} disabled={running} variant="outline" size="sm">
            <Zap className="w-4 h-4 mr-2" />
            Chay AMPC
          </Button>
          <Button onClick={save} disabled={saving} size="sm">
            <Save className="w-4 h-4 mr-2" />
            Luu
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-5 gap-3">
        {fields.map(([field, label, suffix]) => (
          <div key={field} className="space-y-1.5">
            <Label className="text-slate-600" style={{ fontSize: "12px" }}>{label}</Label>
            <div className="flex items-center gap-2">
              <Input
                type="number"
                value={profile[field]}
                onChange={(event) => updateNumber(field, event.target.value)}
              />
              {suffix && <span className="text-slate-400" style={{ fontSize: "11px" }}>{suffix}</span>}
            </div>
          </div>
        ))}
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-5">
        <label className="flex items-center gap-2 text-slate-700" style={{ fontSize: "13px", fontWeight: 700 }}>
          <Switch
            checked={profile.adaptive_enabled}
            onCheckedChange={(checked) => setProfile({ ...profile, adaptive_enabled: checked })}
          />
          Bias correction
        </label>
        <label className="flex items-center gap-2 text-slate-700" style={{ fontSize: "13px", fontWeight: 700 }}>
          <Switch
            checked={profile.actuator_enabled}
            onCheckedChange={(checked) => setProfile({ ...profile, actuator_enabled: checked })}
          />
          Tu dong gui lenh bom
        </label>
        {message && <span className="text-slate-500" style={{ fontSize: "12px" }}>{message}</span>}
      </div>
    </div>
  );
}
