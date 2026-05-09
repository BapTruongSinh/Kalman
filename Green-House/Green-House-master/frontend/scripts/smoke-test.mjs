import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const endpoints = readFileSync(new URL("../src/app/api/endpoints.ts", import.meta.url), "utf8");
const client = readFileSync(new URL("../src/app/api/client.ts", import.meta.url), "utf8");

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

console.log(`frontend smoke tests passed (${requiredPaths.length} API paths)`);
