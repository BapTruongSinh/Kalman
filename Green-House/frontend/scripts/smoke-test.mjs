import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";

const scriptDir = dirname(fileURLToPath(import.meta.url));
const rootDir = resolve(scriptDir, "..");

const endpoints = readFileSync(resolve(rootDir, "src/app/api/endpoints.ts"), "utf8");
const client = readFileSync(resolve(rootDir, "src/app/api/client.ts"), "utf8");

const requiredPaths = [
  "/auth/login/",
  "/dashboard/overview/",
  "/sensor-readings/latest/",
  "/forecast/",
  "/auto-settings/",
  "/control/auto-recommendation/",
  "/devices/",
  "/alerts/",
];

for (const path of requiredPaths) {
  assert.ok(endpoints.includes(path), `missing API path ${path}`);
}

assert.ok(client.includes("baseURL: API_BASE"), "apiClient must use the /api base URL");
assert.ok(client.includes("Authorization"), "apiClient must attach Authorization header");

const sampleProfile = {
  crop_name: "Tomato",
  crop_kc: 1,
  latitude: 16.0471,
  longitude: 108.2068,
  soil_type: "loam",
  theta_fc: 0.32,
  theta_wp: 0.15,
  theta_sat: 0.45,
  root_depth_m: 0.3,
  depletion_fraction_p: 0.5,
  pump_efficiency: 0.8,
  pump_flow_lps: 0.02,
  irrigation_area_m2: 0.25,
  target_low: 55,
  target_high: 65,
  step_seconds: 300,
  horizon_steps: 12,
  pump_min_seconds: 0,
  pump_max_seconds: 300,
  pump_grid_seconds: 30,
  soft_daily_pump_cap_seconds: 1800,
  weight_band: 10,
  weight_water: 0.2,
  weight_switch: 0.5,
  weight_daily: 2,
  weight_terminal: 20,
  adaptive_enabled: false,
  adaptive_bias_window: 12,
  adaptive_max_abs_bias: 5,
  stale_after_seconds: 600,
  actuator_enabled: false,
  updated_at: "2026-05-12T00:00:00Z",
};

const vite = await createServer({
  root: rootDir,
  logLevel: "error",
  appType: "custom",
  server: { middlewareMode: true },
});

try {
  const configModule = await vite.ssrLoadModule("/src/app/components/autoSettingsConfig.ts");
  const autoSettingsModule = await vite.ssrLoadModule("/src/app/components/AutoSettings.tsx");

  const {
    applySoilPreset,
    buildAutoSettingsPayload,
    FAO_SOIL_PRESETS,
    readAutoSettingsError,
    validateAutoSettings,
  } = configModule;
  const { AutoSettingsForm } = autoSettingsModule;

  assert.deepEqual(Object.keys(FAO_SOIL_PRESETS), ["sand", "light_loam", "loam", "clay_loam"]);
  assert.deepEqual(
    applySoilPreset(sampleProfile, "light_loam"),
    {
      ...sampleProfile,
      soil_type: "light_loam",
      theta_fc: 0.15,
      theta_wp: 0.06,
      theta_sat: 0.45,
    },
    "soil preset must update theta fields at runtime",
  );

  const editedAfterPreset = {
    ...applySoilPreset(sampleProfile, "clay_loam"),
    theta_fc: 0.36,
    theta_wp: 0.24,
    theta_sat: 0.46,
  };
  const payload = buildAutoSettingsPayload(editedAfterPreset);
  assert.equal(payload.soil_type, "clay_loam");
  assert.equal(payload.theta_fc, 0.36);
  assert.equal(payload.theta_wp, 0.24);
  assert.equal(payload.theta_sat, 0.46);
  assert.equal(payload.crop_name, undefined, "save payload should not send display-only crop_name");
  assert.equal(payload.updated_at, undefined, "save payload should not send read-only updated_at");

  for (const [field, value] of Object.entries({
    crop_kc: -0.1,
    weight_band: -1,
    weight_water: -1,
    weight_switch: -1,
    weight_daily: -1,
    weight_terminal: -1,
    soft_daily_pump_cap_seconds: 0,
  })) {
    const invalidProfile = { ...sampleProfile, [field]: value };
    assert.notEqual(
      validateAutoSettings(invalidProfile),
      "",
      `validateAutoSettings must reject invalid ${field}`,
    );
  }

  assert.equal(
    readAutoSettingsError({ response: { data: { crop_kc: ["crop_kc must be >= 0"] } } }),
    "crop_kc must be >= 0",
  );

  const markup = renderToStaticMarkup(
    React.createElement(AutoSettingsForm, {
      profile: sampleProfile,
      saving: false,
      message: "",
      error: "crop_kc must be >= 0",
      onSave: () => undefined,
      onNumberChange: () => undefined,
      onSoilTypeChange: () => undefined,
      onAdaptiveEnabledChange: () => undefined,
      onActuatorEnabledChange: () => undefined,
    }),
  );

  assert.ok(markup.includes('data-testid="auto-settings-form"'), "AutoSettingsForm must render loaded form state");
  assert.ok(markup.includes('data-testid="auto-settings-crop-kc"'), "AutoSettingsForm must render crop_kc from profile");
  assert.ok(markup.includes('value="1"'), "AutoSettingsForm must render API response numeric values");
  assert.ok(markup.includes('role="alert"'), "AutoSettingsForm must render API validation errors as alerts");
} finally {
  await vite.close();
}

console.log(`frontend smoke tests passed (${requiredPaths.length} API paths, executable FAO settings checks)`);
