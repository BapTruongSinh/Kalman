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
  const forecastModule = await vite.ssrLoadModule("/src/app/components/ForecastPage.tsx");

  const {
    applySoilPreset,
    buildAutoSettingsPayload,
    FAO_SOIL_PRESETS,
    readAutoSettingsError,
    validateAutoSettings,
  } = configModule;
  const { AutoSettingsForm } = autoSettingsModule;
  const {
    FaoAuditPanel,
    buildAmpcError,
    buildForecastChartData,
    describeFaoStressStatus,
  } = forecastModule;

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

  const sampleRecommendation = {
    id: 101,
    sensor_data: 201,
    estimation: 301,
    device_command: null,
    mode: "AUTO",
    pump_seconds: 45,
    step_seconds: 300,
    predicted_soil_moisture: [62, 61.5, 61],
    target_band: { low: 55, high: 65 },
    objective_cost: 1.25,
    safety_status: "safe",
    reason: "ok",
    bias_correction: 0,
    bias_window_count: 0,
    used_today_pump_seconds: 45,
    command_created: false,
    actuator_status: "disabled",
    created_at: "2026-05-12T00:00:00Z",
  };

  assert.equal(describeFaoStressStatus({ initial_dr: 0, raw: 25 }).tone, "wet");
  assert.equal(describeFaoStressStatus({ initial_dr: 12, raw: 25 }).tone, "safe");
  assert.equal(describeFaoStressStatus({ initial_dr: 30, raw: 25 }).tone, "stress");

  const recommendationWithAudit = {
    ...sampleRecommendation,
    state_snapshot: {
      fao56: {
        initial_theta: 0.315,
        initial_dr: 1.5,
        taw: 51,
        raw: 25.5,
        ks: 1,
        et0_step: 0.05,
        etc_adj: 0.05,
        irrigation_depth_mm: 19.2,
        predicted_dr: [1.5, 0],
        predicted_soil_moisture: [62, 64],
      },
    },
  };
  const faoMarkup = renderToStaticMarkup(
    React.createElement(FaoAuditPanel, { recommendation: recommendationWithAudit }),
  );

  assert.ok(faoMarkup.includes('data-testid="fao-audit-panel"'), "FAO audit panel must render");
  assert.ok(faoMarkup.includes('data-testid="fao-stress-status"'), "FAO panel must render stress status");
  assert.ok(faoMarkup.includes("Safe zone"), "FAO panel must classify Dr <= RAW as safe");
  assert.ok(faoMarkup.includes("Dr"), "FAO panel must render Dr diagnostic");
  assert.ok(faoMarkup.includes("TAW"), "FAO panel must render TAW diagnostic");
  assert.ok(faoMarkup.includes("RAW"), "FAO panel must render RAW diagnostic");
  assert.ok(faoMarkup.includes("Ks"), "FAO panel must render Ks diagnostic");
  assert.ok(faoMarkup.includes("ET0_step"), "FAO panel must render ET0_step diagnostic");
  assert.ok(faoMarkup.includes("ETc_adj"), "FAO panel must render ETc_adj diagnostic");
  assert.ok(
    faoMarkup.includes("irrigation_depth_mm"),
    "FAO panel must render irrigation_depth_mm diagnostic",
  );
  assert.ok(faoMarkup.includes("1.50 mm"), "FAO panel must format FAO millimeter values");

  const noAuditMarkup = renderToStaticMarkup(
    React.createElement(FaoAuditPanel, { recommendation: sampleRecommendation }),
  );
  assert.ok(noAuditMarkup.includes('data-testid="fao-audit-panel"'), "FAO panel must render without audit data");
  assert.ok(noAuditMarkup.includes("--"), "FAO panel must use null-safe placeholders without audit data");

  const forecastRows = buildForecastChartData({
    latest: {
      id: 1,
      temperature: 30,
      humidity: 70,
      light: 450,
      soil_moisture: 60,
      recorded_at: "2026-05-12T00:00:00Z",
    },
    estimation: null,
    recommendation: recommendationWithAudit,
    scheduler: null,
    history: [],
  });
  assert.deepEqual(
    forecastRows.filter((row) => row.soilForecast !== null).map((row) => row.soilForecast),
    [62, 61.5, 61],
    "forecast chart must keep using recommendation.predicted_soil_moisture percent values",
  );

  const ampcError = buildAmpcError(
    {
      ...sampleRecommendation,
      safety_status: "config_error",
      reason: 'ValueError: root_depth_m must be > 0\nFile "api/ampc.py", line 134',
    },
    null,
  );
  assert.ok(!ampcError.includes("ValueError"), "AMPC error UI must not leak exception names");
  assert.ok(!ampcError.includes("api/ampc.py"), "AMPC error UI must not leak backend file paths");
} finally {
  await vite.close();
}

console.log(`frontend smoke tests passed (${requiredPaths.length} API paths, FAO settings and forecast audit checks)`);
