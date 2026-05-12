import { useEffect, useState } from "react";
import { Save } from "lucide-react";

import type { ControlProfile, FaoSoilType } from "../api/endpoints";
import {
  getAutoSettings,
  updateAutoSettings,
} from "../api/endpoints";
import {
  applySoilPreset,
  AUTO_SETTINGS_NUMERIC_GROUPS,
  buildAutoSettingsPayload,
  FAO_SOIL_OPTIONS,
  FAO_SOIL_PRESETS,
  isFaoSoilType,
  readAutoSettingsError,
  validateAutoSettings,
} from "./autoSettingsConfig";
import type { AutoSettingsNumericField } from "./autoSettingsConfig";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "./ui/select";
import { Switch } from "./ui/switch";

function toNumber(value: string): number {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : 0;
}

function fieldTestId(field: string): string {
  return `auto-settings-${field.replaceAll("_", "-")}`;
}

export type AutoSettingsFormProps = {
  profile: ControlProfile;
  saving: boolean;
  message: string;
  error: string;
  onSave: () => void;
  onNumberChange: (field: AutoSettingsNumericField, value: string) => void;
  onSoilTypeChange: (soilType: FaoSoilType) => void;
  onAdaptiveEnabledChange: (checked: boolean) => void;
  onActuatorEnabledChange: (checked: boolean) => void;
};

export function AutoSettings() {
  const [profile, setProfile] = useState<ControlProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    getAutoSettings()
      .then((response) => {
        if (!cancelled) {
          setProfile(response.data);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setError("Không tải được cấu hình AMPC.");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const updateNumber = (field: AutoSettingsNumericField, value: string): void => {
    setProfile((current) => current ? { ...current, [field]: toNumber(value) } : current);
  };

  const updateSoilType = (soilType: FaoSoilType): void => {
    setProfile((current) => current ? applySoilPreset(current, soilType) : current);
  };

  const save = async (): Promise<void> => {
    if (!profile) return;

    const validationError = validateAutoSettings(profile);
    if (validationError) {
      setMessage("");
      setError(validationError);
      return;
    }

    setSaving(true);
    setMessage("");
    setError("");
    try {
      const response = await updateAutoSettings(buildAutoSettingsPayload(profile));
      setProfile(response.data);
      setMessage("Đã lưu cấu hình AMPC.");
    } catch (err) {
      setError(readAutoSettingsError(err));
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="elevated-card rounded-3xl p-5" data-testid="auto-settings-loading">
        <p className="text-slate-500" style={{ fontSize: "13px" }}>Đang tải cấu hình AMPC...</p>
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="elevated-card rounded-3xl p-5" data-testid="auto-settings-error">
        <p className="text-red-700" style={{ fontSize: "13px", fontWeight: 700 }}>
          {error || "Không tải được cấu hình AMPC."}
        </p>
      </div>
    );
  }

  return (
    <AutoSettingsForm
      profile={profile}
      saving={saving}
      message={message}
      error={error}
      onSave={save}
      onNumberChange={updateNumber}
      onSoilTypeChange={updateSoilType}
      onAdaptiveEnabledChange={(checked) => setProfile({ ...profile, adaptive_enabled: checked })}
      onActuatorEnabledChange={(checked) => setProfile({ ...profile, actuator_enabled: checked })}
    />
  );
}

export function AutoSettingsForm({
  profile,
  saving,
  message,
  error,
  onSave,
  onNumberChange,
  onSoilTypeChange,
  onAdaptiveEnabledChange,
  onActuatorEnabledChange,
}: AutoSettingsFormProps) {
  return (
    <div className="elevated-card rounded-3xl p-5" data-testid="auto-settings-form">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <div>
          <p className="text-slate-800" style={{ fontSize: "15px", fontWeight: 800 }}>
            Cấu hình AMPC
          </p>
          <p className="text-slate-500" style={{ fontSize: "12px" }}>
            Lưu cấu hình FAO-56 cho mô hình Dr/RAW và giữ các ngưỡng sensor % để hiển thị legacy.
          </p>
        </div>
        <Button onClick={onSave} disabled={saving} size="sm" data-testid="auto-settings-save">
          <Save className="w-4 h-4 mr-2" />
          {saving ? "Đang lưu" : "Lưu"}
        </Button>
      </div>

      <div className="rounded-2xl border border-amber-100 bg-amber-50 px-4 py-3 text-amber-800" style={{ fontSize: "12px" }}>
        Sensor độ ẩm đất trả về phần trăm trên thang cảm biến 0-100. Các trường theta bên dưới là độ ẩm thể tích m3/m3 dùng cho FAO-56, không phải cùng một đơn vị.
      </div>

      <div className="mt-5 grid grid-cols-1 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,2fr)] gap-6 border-t border-slate-100 pt-4">
        <div className="space-y-3">
          <Label className="text-slate-600" style={{ fontSize: "12px" }}>Loại đất</Label>
          <Select
            value={profile.soil_type}
            onValueChange={(value) => {
              if (isFaoSoilType(value)) {
                onSoilTypeChange(value);
              }
            }}
          >
            <SelectTrigger className="mt-2 bg-white" data-testid="auto-settings-soil-type">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {FAO_SOIL_OPTIONS.map((soilType) => (
                <SelectItem key={soilType} value={soilType}>
                  {FAO_SOIL_PRESETS[soilType].label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <div className="mt-3 grid grid-cols-3 gap-2 text-slate-600" style={{ fontSize: "11px" }}>
            <span>FC {profile.theta_fc.toFixed(2)}</span>
            <span>WP {profile.theta_wp.toFixed(2)}</span>
            <span>SAT {profile.theta_sat.toFixed(2)}</span>
          </div>
          <p className="mt-3 text-slate-500" style={{ fontSize: "11px" }}>
            Chọn preset sẽ điền theta_fc, theta_wp, theta_sat. Bạn vẫn có thể sửa các giá trị theta sau đó trước khi lưu.
          </p>
        </div>

        <div className="space-y-5">
          {AUTO_SETTINGS_NUMERIC_GROUPS.map((group) => (
            <section key={group.title} className="space-y-3">
              <div>
                <p className="text-slate-700" style={{ fontSize: "12px", fontWeight: 800 }}>{group.title}</p>
                <p className="text-slate-500 mt-1" style={{ fontSize: "11px" }}>{group.description}</p>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
                {group.fields.map((field) => (
                  <div key={field.field} className="space-y-1.5">
                    <Label className="text-slate-600" style={{ fontSize: "12px" }} htmlFor={fieldTestId(field.field)}>
                      {field.label}
                    </Label>
                    <div className="flex items-center gap-2">
                      <Input
                        id={fieldTestId(field.field)}
                        data-testid={fieldTestId(field.field)}
                        type="number"
                        value={profile[field.field]}
                        step={field.step}
                        min={field.min}
                        max={field.max}
                        onChange={(event) => onNumberChange(field.field, event.target.value)}
                        aria-invalid={Boolean(error)}
                      />
                      {field.suffix && <span className="text-slate-400 shrink-0" style={{ fontSize: "11px" }}>{field.suffix}</span>}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          ))}
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-5">
        <label className="flex items-center gap-2 text-slate-700" style={{ fontSize: "13px", fontWeight: 700 }}>
          <Switch
            checked={profile.adaptive_enabled}
            onCheckedChange={onAdaptiveEnabledChange}
            data-testid="auto-settings-adaptive-enabled"
          />
          Bù sai số thích nghi
        </label>
        <label className="flex items-center gap-2 text-slate-700" style={{ fontSize: "13px", fontWeight: 700 }}>
          <Switch
            checked={profile.actuator_enabled}
            onCheckedChange={onActuatorEnabledChange}
            data-testid="auto-settings-actuator-enabled"
          />
          Tự động gửi lệnh bơm
        </label>
      </div>

      {(message || error) && (
        <p
          className={error ? "mt-4 text-red-700" : "mt-4 text-slate-500"}
          style={{ fontSize: "12px", fontWeight: error ? 700 : 500 }}
          role={error ? "alert" : "status"}
          data-testid="auto-settings-message"
        >
          {error || message}
        </p>
      )}
    </div>
  );
}
