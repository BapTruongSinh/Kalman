import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const endpoints = readFileSync(new URL("../src/app/api/endpoints.ts", import.meta.url), "utf8");
const client = readFileSync(new URL("../src/app/api/client.ts", import.meta.url), "utf8");
const autoSettings = readFileSync(new URL("../src/app/components/AutoSettings.tsx", import.meta.url), "utf8");
const autoSettingsConfig = readFileSync(new URL("../src/app/components/autoSettingsConfig.ts", import.meta.url), "utf8");

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

assert.ok(client.includes('baseURL: API_BASE'), "apiClient must use the /api base URL");
assert.ok(client.includes('Authorization'), "apiClient must attach Authorization header");

const faoFields = [
  "crop_kc",
  "latitude",
  "longitude",
  "soil_type",
  "theta_fc",
  "theta_wp",
  "theta_sat",
  "root_depth_m",
  "depletion_fraction_p",
  "pump_efficiency",
  "pump_flow_lps",
  "irrigation_area_m2",
];

for (const field of faoFields) {
  assert.ok(endpoints.includes(field), `ControlProfile missing FAO field ${field}`);
  assert.ok(autoSettingsConfig.includes(`"${field}"`), `auto settings payload/config missing ${field}`);
}

const presetChecks = [
  ['sand', 'theta_fc: 0.1', 'theta_wp: 0.04', 'theta_sat: 0.45'],
  ['light_loam', 'theta_fc: 0.15', 'theta_wp: 0.06', 'theta_sat: 0.45'],
  ['loam', 'theta_fc: 0.32', 'theta_wp: 0.15', 'theta_sat: 0.45'],
  ['clay_loam', 'theta_fc: 0.35', 'theta_wp: 0.23', 'theta_sat: 0.45'],
];

for (const [soilType, thetaFc, thetaWp, thetaSat] of presetChecks) {
  assert.ok(autoSettingsConfig.includes(soilType), `missing soil preset ${soilType}`);
  assert.ok(autoSettingsConfig.includes(thetaFc), `${soilType} missing ${thetaFc}`);
  assert.ok(autoSettingsConfig.includes(thetaWp), `${soilType} missing ${thetaWp}`);
  assert.ok(autoSettingsConfig.includes(thetaSat), `${soilType} missing ${thetaSat}`);
}

assert.ok(autoSettings.includes("profile[field.field]"), "AutoSettings must render numeric fields from API response profile values");
assert.ok(autoSettings.includes("applySoilPreset"), "AutoSettings must apply soil presets when soil type changes");
assert.ok(autoSettings.includes("buildAutoSettingsPayload"), "AutoSettings save must use the FAO payload builder");
assert.ok(autoSettings.includes("readAutoSettingsError"), "AutoSettings must display API validation errors");
assert.ok(autoSettings.includes("role={error ? \"alert\" : \"status\"}"), "AutoSettings must expose validation errors to assistive tech");

console.log(`frontend smoke tests passed (${requiredPaths.length} API paths, ${faoFields.length} FAO fields)`);
