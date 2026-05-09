# FAO MPC Water-Balance Implementation Plan

## Summary

- Chuyen MPC/AMPC tu plant ARX du doan truc tiep do am dat sang mo hinh can bang nuoc theo FAO.
- Van giu bien dieu khien `u_k` la so giay bat bom (`pump_seconds`), nhung MPC se toi uu `u_k` dua tren `Dr`, `ETc`, va luong tuoi `I(u_k)`.
- Dung Open-Meteo de lay truc tiep `et0_fao_evapotranspiration`, khong tu tinh Penman-Monteith trong ban dau.
- Vi tri mac dinh la Da Nang, Viet Nam: `latitude=16.0544`, `longitude=108.2022`, `timezone=Asia/Bangkok`.
- Backend goi Open-Meteo khi start hoac khi cache ET0 qua 1 gio.

## Target Model

FAO-56 dung de tinh cay va moi truong lam mat bao nhieu nuoc. MPC dung de quyet dinh nen bom bao nhieu giay.

State equation:

```text
Dr(k+1) = Dr(k) + ETc(k) - I(u_k)
```

Pump-to-irrigation conversion:

```text
I(u_k) = (eta * Q / A) * u_k
```

Where:

- `u_k`: so giay bat bom tai step k.
- `I(u_k)`: luong nuoc tuoi tao ra boi `u_k`, don vi mm.
- `Dr(k)`: depletion, luong nuoc dang thieu trong vung re, don vi mm.
- `ETc(k)`: crop evapotranspiration trong step k, don vi mm/step.
- `eta`: hieu suat he thong tuoi.
- `Q`: luu luong bom, don vi L/s.
- `A`: dien tich tuoi hieu dung, don vi m2.

## Weather Source

Dung Open-Meteo Forecast API:

```text
https://api.open-meteo.com/v1/forecast?latitude=16.0544&longitude=108.2022&hourly=et0_fao_evapotranspiration&timezone=Asia%2FBangkok
```

Expected response shape:

```json
{
  "hourly": {
    "time": ["2026-05-10T00:00", "2026-05-10T01:00"],
    "et0_fao_evapotranspiration": [0.01, 0.02]
  }
}
```

Runtime policy:

- Cache ET0 theo gio.
- Neu backend moi start va chua co cache thi goi Open-Meteo ngay.
- Neu cache moi hon 1 gio thi dung cache, khong goi lai API.
- Neu API loi hoac khong co ET0 hop le thi AMPC fail-safe: `pump_seconds=0`, khong gui lenh bom xuong ESP32, reason ro rang.
- Horizon 60 phut voi step 5 phut dung ET0 cua gio tuong ung; neu horizon vuot qua ranh gio thi lay ET0 cua gio tiep theo.

## FAO Computation

Ban dau dung single crop coefficient:

```text
ETc = Kc * Ks * ET0
```

Convert ET0 hourly to step:

```text
ET0_step = ET0_hour * step_seconds / 3600
ETc_step = Kc * Ks * ET0_step
```

Soil water capacity:

```text
TAW = 1000 * (theta_fc - theta_wp) * Zr
RAW = p * TAW
```

Water stress coefficient:

```text
Ks = 1, if Dr <= RAW
Ks = (TAW - Dr) / ((1 - p) * TAW), if Dr > RAW
Ks = clamp(Ks, 0, 1)
```

Sensor percent to volumetric water content:

```text
theta = theta_wp + soil_percent / 100 * (theta_fc - theta_wp)
```

Current depletion:

```text
Dr = 1000 * (theta_fc - theta) * Zr
Dr = clamp(Dr, 0, TAW)
```

Predicted depletion back to UI soil percent:

```text
theta = theta_fc - Dr / (1000 * Zr)
soil_percent = 100 * (theta - theta_wp) / (theta_fc - theta_wp)
soil_percent = clamp(soil_percent, 0, 100)
```

## Defaults

Soil presets:

| soil_type | theta_fc | theta_wp |
| --- | ---: | ---: |
| sand | 0.10 | 0.04 |
| sandy_loam | 0.15 | 0.06 |
| loam | 0.32 | 0.15 |
| clay_loam | 0.35 | 0.23 |

Default runtime values:

| Field | Default |
| --- | ---: |
| `soil_type` | `loam` |
| `theta_fc` | `0.32` |
| `theta_wp` | `0.15` |
| `root_depth_m` | `0.30` |
| `depletion_fraction_p` | `0.50` |
| `irrigation_area_m2` | `0.25` |
| `pump_flow_lps` | `0.02` |
| `irrigation_efficiency` | `0.80` |
| `target_depletion_mm` | `RAW / 2` |
| `crop_kc` | current UI/profile value |
| `latitude` | `16.0544` |
| `longitude` | `108.2022` |
| `timezone` | `Asia/Bangkok` |

## MPC Runtime Flow

```text
Sensor soil moisture %
        |
Kalman filter / raw fallback
        |
Convert soil % -> theta -> Dr
        |
Load cached Open-Meteo ET0
        |
Compute TAW, RAW, Ks, ETc_step
        |
MPC tries pump_seconds sequences
        |
For each u_k:
  I(u_k) = (eta * Q / A) * u_k
  Dr(k+1) = Dr(k) + ETc(k) - I(u_k)
        |
Score trajectory
        |
Choose first pump_seconds
        |
Persist recommendation
        |
If auto mode and safe: queue pump command for ESP32
```

## Implementation Changes

### MPC package

- Add FAO config dataclasses for soil, irrigation, crop, and weather location.
- Add FAO calculation helpers for `TAW`, `RAW`, `Ks`, ET0 step conversion, depletion conversion, and pump-water conversion.
- Add `FAOWaterBalancePlantModel` implementing the existing `PlantModel` interface.
- Keep `GridShootingSolver` interface unchanged: it still optimizes `pump_seconds`.
- Change default simulation/recommendation path to FAO plant when FAO config is present.
- Keep ARX plant available as legacy/dev comparison path if existing tests or docs still need it.

### Green-House backend

- Extend `GreenhouseControlProfile` with FAO fields:
  - `soil_type`
  - `theta_fc`
  - `theta_wp`
  - `root_depth_m`
  - `depletion_fraction_p`
  - `target_depletion_mm`
  - `irrigation_area_m2`
  - `pump_flow_lps`
  - `irrigation_efficiency`
  - `weather_latitude`
  - `weather_longitude`
  - `weather_timezone`
- Add Open-Meteo ET0 fetch/cache service.
- Change `run_auto_recommendation()` to use `FAOWaterBalancePlantModel` instead of `ARXPlantModel` for AMPC runtime.
- Keep Kalman estimator unchanged; Kalman still provides filtered/current soil moisture.
- Persist FAO diagnostics into `config_snapshot` and `state_snapshot`.
- If FAO config invalid, ET0 missing, stale sample, or solver error: persist unsafe recommendation with `pump_seconds=0` and do not queue pump command.

### Frontend

- Extend Auto Settings type and UI with FAO fields.
- Show units clearly:
  - `m2` for area.
  - `L/s` for pump flow.
  - `m` for root depth.
  - `mm` for depletion.
  - `%` for soil moisture.
- Forecast page should keep showing predicted soil moisture %, but can show extra diagnostics:
  - `Dr hien tai`
  - `ET0 gio hien tai`
  - `ETc moi step`
  - `TAW`
  - `RAW`
  - `Ks`

## Public Interface Changes

Recommendation output remains compatible:

```json
{
  "pump_seconds": 109.0,
  "step_seconds": 300,
  "predicted_soil_moisture": [58.2, 58.0, 57.8],
  "target_band": {"low": 55.0, "high": 65.0},
  "cost": 12.34,
  "safety_status": "safe",
  "reason": "below_target_depletion"
}
```

`config_snapshot` adds:

```json
{
  "fao": {
    "enabled": true,
    "soil_type": "loam",
    "theta_fc": 0.32,
    "theta_wp": 0.15,
    "root_depth_m": 0.3,
    "depletion_fraction_p": 0.5,
    "irrigation_area_m2": 0.25,
    "pump_flow_lps": 0.02,
    "irrigation_efficiency": 0.8,
    "crop_kc": 1.0,
    "latitude": 16.0544,
    "longitude": 108.2022
  }
}
```

`state_snapshot` adds:

```json
{
  "theta_current": 0.278,
  "depletion_mm": 12.6,
  "taw_mm": 51.0,
  "raw_mm": 25.5,
  "ks": 1.0,
  "et0_hour_mm": 0.02,
  "etc_step_mm": 0.0017,
  "used_weather_cache_at": "2026-05-10T01:00:00+07:00"
}
```

## Test Plan

### MPC unit tests

- Soil percent to theta to Dr conversion is correct.
- Dr to soil percent conversion is correct.
- `TAW`, `RAW`, and `Ks` match FAO formulas.
- `ET0_hour` converts to `ET0_step` by `step_seconds / 3600`.
- `I(u) = eta * Q / A * u` is correct.
- `Dr_next` increases with ETc and no irrigation.
- `Dr_next` decreases when pump is on.
- Solver recommends `pump_seconds > 0` when depletion is above target.
- Solver recommends `pump_seconds=0` when soil is already wet enough.

### Backend tests

- Open-Meteo response is parsed correctly.
- ET0 cache prevents repeated API calls within 1 hour.
- Missing ET0 makes AMPC fail-safe and does not queue pump command.
- Invalid FAO profile fields make AMPC fail-safe.
- Auto settings save FAO fields and runtime uses them.
- Recommendation snapshots include FAO diagnostics.

### Frontend tests

- Auto Settings loads and saves FAO fields.
- Forecast page renders FAO diagnostics when present.
- Forecast page shows AMPC error when ET0/config is missing.

### Validation gates

```text
python -m pytest MPC/tests -q
python manage.py test api -v 1
python manage.py check
python manage.py makemigrations --check --dry-run
npm test
npm run build
```

## Assumptions

- Open-Meteo ET0 is trusted as FAO ET0 source for this project.
- No need to calculate net radiation, soil heat flux, wind, or vapor pressure manually in this version.
- `crop_kc` already exists in UI/profile and will be reused.
- ESP32 protocol remains unchanged: backend still sends `pump_seconds`.
- Multi-greenhouse precision can be improved later; current defaults target the active/default greenhouse.
