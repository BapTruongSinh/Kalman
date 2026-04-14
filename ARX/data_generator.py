import numpy as np
import pandas as pd


TRUE_PARAMS = {
    "a1": 0.965,
    "a2": 0.025,
    "b_temp_1": -0.008,
    "b_temp_2": -0.004,
    "b_humi_1": 0.0025,
    "b_humi_2": 0.0012,
    "b_light_1": -0.00022,
    "b_light_2": -0.00010,
    "b_drip_1": 1.25,
    "b_drip_2": 1.85,
    "b_mist_1": 0.05,
    "b_mist_2": 0.03,
    "b_fan_1": -0.05,
    "b_fan_2": -0.03,
    "b_temp": -0.008,
    "b_humi": 0.0025,
    "b_light": -0.00022,
    "b_drip": 1.25,
    "b_mist": 0.05,
    "b_fan": -0.05,
    "noise_sigma": 0.25,
}


def _month_to_season(month):
    if month in (3, 4, 5):
        return "spring"
    if month in (6, 7, 8):
        return "summer"
    if month in (9, 10, 11):
        return "autumn"
    return "winter"


def _time_of_day_setpoint_adjustment(hour):
    if 10 <= hour < 15:
        return 1.0, 1.0
    if hour >= 20 or hour < 5:
        return -1.0, -1.0
    return 0.0, 0.0


def get_true_params():
    return TRUE_PARAMS.copy()


def generate_greenhouse_data(days=365, T_s=300, seed=42, start_date="2025-01-01"):
    """
    Sinh dữ liệu synthetic cho nhà kính mini theo đúng tinh thần ARX(2,2,1).

    Output:
    - Soil_Moisture là biến mục tiêu
    - Mỗi input tác động với 2 lag: t-1 và t-2
    - Có setpoint, hysteresis, dwell time và môi trường ngày/đêm
    - Mặc định sinh đủ 1 năm để đánh giá mô hình qua nhiều tháng / mùa
    """
    if days <= 0:
        raise ValueError("days must be positive")
    if T_s <= 0:
        raise ValueError("T_s must be positive")

    rng = np.random.default_rng(seed)

    samples_per_day = int(round(24 * 3600 / T_s))
    if samples_per_day < 4:
        raise ValueError("T_s is too large for greenhouse dynamics; expected at least 4 samples per day")

    N = int(days * samples_per_day)
    t = np.arange(N)
    timestamps = pd.date_range(start_date, periods=N, freq=f"{T_s}s")

    hour = (t % samples_per_day) / samples_per_day * 24.0
    months = timestamps.month.to_numpy()
    seasons = np.array([_month_to_season(int(m)) for m in months])

    # Thông số mục tiêu cho mini greenhouse: band hẹp hơn, ẩm đất giữ ổn định hơn.
    monthly_profile = {
        1: {"soil_low": 52.0, "soil_high": 61.0, "temp_offset": -2.0, "humi_offset": 4.0, "light_scale": 0.85},
        2: {"soil_low": 53.0, "soil_high": 62.0, "temp_offset": -1.0, "humi_offset": 3.5, "light_scale": 0.88},
        3: {"soil_low": 54.0, "soil_high": 63.0, "temp_offset": 0.0, "humi_offset": 2.5, "light_scale": 0.92},
        4: {"soil_low": 55.0, "soil_high": 64.0, "temp_offset": 0.8, "humi_offset": 1.8, "light_scale": 0.97},
        5: {"soil_low": 56.0, "soil_high": 65.0, "temp_offset": 1.6, "humi_offset": 0.8, "light_scale": 1.02},
        6: {"soil_low": 57.0, "soil_high": 66.0, "temp_offset": 2.3, "humi_offset": -1.0, "light_scale": 1.05},
        7: {"soil_low": 58.0, "soil_high": 67.0, "temp_offset": 3.0, "humi_offset": -2.5, "light_scale": 1.08},
        8: {"soil_low": 57.0, "soil_high": 66.0, "temp_offset": 2.5, "humi_offset": -1.5, "light_scale": 1.06},
        9: {"soil_low": 55.0, "soil_high": 64.0, "temp_offset": 1.5, "humi_offset": -0.2, "light_scale": 1.00},
        10: {"soil_low": 54.0, "soil_high": 63.0, "temp_offset": 0.7, "humi_offset": 0.8, "light_scale": 0.95},
        11: {"soil_low": 53.0, "soil_high": 62.0, "temp_offset": -0.4, "humi_offset": 2.0, "light_scale": 0.90},
        12: {"soil_low": 52.0, "soil_high": 61.0, "temp_offset": -1.5, "humi_offset": 3.5, "light_scale": 0.86},
    }

    soil_low_base = np.array([monthly_profile[int(m)]["soil_low"] for m in months])
    soil_high_base = np.array([monthly_profile[int(m)]["soil_high"] for m in months])
    seasonal_temp_offset = np.array([monthly_profile[int(m)]["temp_offset"] for m in months])
    seasonal_humi_offset = np.array([monthly_profile[int(m)]["humi_offset"] for m in months])
    seasonal_light_scale = np.array([monthly_profile[int(m)]["light_scale"] for m in months])

    low_adjust = np.where((hour >= 10.0) & (hour < 15.0), 1.0, np.where((hour >= 20.0) | (hour < 5.0), -1.0, 0.0))
    high_adjust = low_adjust.copy()

    soil_low_sp = soil_low_base + low_adjust
    soil_high_sp = soil_high_base + high_adjust

    day_idx = (t // samples_per_day).astype(int)
    day_temp_offset = rng.normal(0.0, 1.8, days + 2)
    day_humi_offset = rng.normal(0.0, 4.5, days + 2)
    day_light_factor = rng.uniform(0.75, 1.15, days + 2)
    day_heat_boost = rng.choice([0.0, 1.8, 2.8], size=days + 2, p=[0.78, 0.17, 0.05])
    day_dry_penalty = rng.choice([0.0, -4.0], size=days + 2, p=[0.82, 0.18])

    daylight_shape = np.sin((hour - 6.0) / 12.0 * np.pi)
    ambient_light = 10.0 + rng.normal(0.0, 2.0, N)
    daylight_mask = (hour >= 6.0) & (hour <= 18.0)
    light_raw = np.where(
        daylight_mask,
        np.maximum(0.0, daylight_shape) * 950.0 * day_light_factor[day_idx] + ambient_light,
        ambient_light,
    )
    Light = np.clip(light_raw * seasonal_light_scale + rng.normal(0.0, 8.0, N), 0.0, 1300.0)

    temp_phase = (hour - 14.0) / 24.0 * 2.0 * np.pi
    outdoor_temp = (
        27.0
        + 6.0 * np.cos(temp_phase)
        + day_temp_offset[day_idx]
        + day_heat_boost[day_idx]
        + seasonal_temp_offset
        + rng.normal(0.0, 0.5, N)  # Tăng nhiễu để tạo excitation
    )
    outdoor_humi = (
        72.0
        - 13.0 * np.cos(temp_phase)
        - 1.5 * day_temp_offset[day_idx]
        + day_dry_penalty[day_idx]
        + day_humi_offset[day_idx]
        + seasonal_humi_offset
        + rng.normal(0.0, 1.8, N)  # Tăng nhiễu để tạo excitation
    )
    outdoor_humi = np.clip(outdoor_humi, 30.0, 98.0)

    TRUE = get_true_params()

    Temp = np.zeros(N)
    Humi = np.zeros(N)
    Drip = np.zeros(N)
    Mist = np.zeros(N)
    Fan = np.zeros(N)
    y = np.zeros(N)

    Temp[0] = outdoor_temp[0]
    Temp[1] = outdoor_temp[1]
    Humi[0] = outdoor_humi[0]
    Humi[1] = outdoor_humi[1]
    y[0], y[1] = 58.0, 57.8

    min_drip_switch_steps = max(2, int(round(600 / T_s)))  # ~10 phút
    min_mist_switch_steps = max(2, int(round(600 / T_s)))  # ~10 phút
    min_fan_switch_steps = max(2, int(round(600 / T_s)))   # ~10 phút
    last_drip_switch = 0
    last_mist_switch = 0
    last_fan_switch = 0
    drip_pulse_remaining = 0
    mist_pulse_remaining = 0
    fan_probe_remaining = 0
    low_count = 0

    for i in range(2, N):
        low_sp = soil_low_sp[i - 1]
        high_sp = soil_high_sp[i - 1]
        low_count = low_count + 1 if y[i - 1] < low_sp else 0

        drip_can_switch = (i - last_drip_switch) >= min_drip_switch_steps
        fan_can_switch = (i - last_fan_switch) >= min_fan_switch_steps
        mist_can_switch = (i - last_mist_switch) >= min_mist_switch_steps

        if drip_pulse_remaining > 0:
            Drip[i] = 1.0
            drip_pulse_remaining -= 1
        else:
            if low_count >= 2 and y[i - 1] <= (high_sp - 1.0) and drip_can_switch:
                Drip[i] = 1.0
                drip_pulse_remaining = max(0, int(round(600 / T_s)) - 1)
                last_drip_switch = i
            else:
                Drip[i] = 0.0

        if fan_probe_remaining > 0:
            Fan[i] = 1.0
            fan_probe_remaining -= 1
        elif Fan[i - 1] < 0.5:
            if fan_can_switch and (Temp[i - 1] > 29.5 or Humi[i - 1] > 85.0):
                Fan[i] = 1.0
                last_fan_switch = i
            else:
                Fan[i] = 0.0
        else:
            if fan_can_switch and Temp[i - 1] < 27.5 and Humi[i - 1] < 80.0:
                Fan[i] = 0.0
                last_fan_switch = i
            else:
                Fan[i] = 1.0

        if mist_pulse_remaining > 0:
            Mist[i] = 1.0
            mist_pulse_remaining -= 1
        elif Mist[i - 1] < 0.5:
            if mist_can_switch and Temp[i - 1] > 29.0 and Humi[i - 1] < 66.0:
                Mist[i] = 1.0
                mist_pulse_remaining = max(0, int(round(600 / T_s)) - 1)
                last_mist_switch = i
            else:
                Mist[i] = 0.0
        else:
            if mist_can_switch and (Temp[i - 1] < 27.0 or Humi[i - 1] > 74.0):
                Mist[i] = 0.0
                last_mist_switch = i
            else:
                Mist[i] = 1.0

        # Persistent excitation an toàn cho nhận dạng hệ:
        # chèn các pulse nhỏ khi hệ đang ở vùng an toàn, tránh data quá "đều".
        if (
            drip_pulse_remaining == 0
            and Drip[i] < 0.5
            and drip_can_switch
            and (low_sp + 1.0) <= y[i - 1] <= (high_sp - 1.5)
            and rng.random() < 0.006
        ):
            Drip[i] = 1.0
            drip_pulse_remaining = max(0, int(round(600 / T_s)) - 1)
            last_drip_switch = i

        if (
            mist_pulse_remaining == 0
            and Mist[i] < 0.5
            and mist_can_switch
            and Temp[i - 1] > 28.0
            and 58.0 <= Humi[i - 1] <= 72.0
            and rng.random() < 0.004
        ):
            Mist[i] = 1.0
            mist_pulse_remaining = max(0, int(round(600 / T_s)) - 1)
            last_mist_switch = i

        if (
            fan_probe_remaining == 0
            and Fan[i] < 0.5
            and fan_can_switch
            and 26.0 <= Temp[i - 1] <= 30.0
            and 65.0 <= Humi[i - 1] <= 82.0
            and rng.random() < 0.005
        ):
            Fan[i] = 1.0
            fan_probe_remaining = max(0, int(round(600 / T_s)) - 1)
            last_fan_switch = i

        # Môi trường trong nhà kính có quán tính, không đổi tức thời hoàn toàn.
        Temp[i] = (
            0.86 * Temp[i - 1]
            + 0.14 * outdoor_temp[i]
            - 1.35 * Fan[i]
            - 1.40 * Mist[i]
            + rng.normal(0.0, 0.3)  # Excitation ngắn hạn cho quán tính nhiệt
        )
        Humi[i] = (
            0.84 * Humi[i - 1]
            + 0.16 * outdoor_humi[i]
            + 11.0 * Mist[i]
            - 3.8 * Fan[i]
            + rng.normal(0.0, 0.8)  # Excitation ngắn hạn cho quán tính ẩm
        )
        Temp[i] = np.clip(Temp[i], 14.0, 42.0)
        Humi[i] = np.clip(Humi[i], 30.0, 100.0)

        y[i] = (
            TRUE["a1"] * y[i - 1]
            + TRUE["a2"] * y[i - 2]
            + TRUE["b_temp_1"] * Temp[i - 1]
            + TRUE["b_temp_2"] * Temp[i - 2]
            + TRUE["b_humi_1"] * Humi[i - 1]
            + TRUE["b_humi_2"] * Humi[i - 2]
            + TRUE["b_light_1"] * Light[i - 1]
            + TRUE["b_light_2"] * Light[i - 2]
            + TRUE["b_drip_1"] * Drip[i - 1]
            + TRUE["b_drip_2"] * Drip[i - 2]
            + TRUE["b_mist_1"] * Mist[i - 1]
            + TRUE["b_mist_2"] * Mist[i - 2]
            + TRUE["b_fan_1"] * Fan[i - 1]
            + TRUE["b_fan_2"] * Fan[i - 2]
            + rng.normal(0.0, TRUE["noise_sigma"])
        )
        y[i] = np.clip(y[i], 10.0, 100.0)

    df = pd.DataFrame(
        {
            "Timestamp": timestamps,
            "Month": months,
            "Season": seasons,
            "Soil_Moisture": y,
            "Soil_Low_SP": soil_low_sp,
            "Soil_High_SP": soil_high_sp,
            "Temperature": Temp,
            "Humidity": Humi,
            "Light": Light,
            "Drip": Drip,
            "Mist": Mist,
            "Fan": Fan,
        }
    )

    return df, TRUE


if __name__ == "__main__":
    df, TRUE = generate_greenhouse_data(days=365, T_s=300, seed=42)
    print("Dataset Shape:", df.shape)
    print("Date range:", df["Timestamp"].iloc[0], "->", df["Timestamp"].iloc[-1])
    print("Months present:", sorted(df["Month"].unique().tolist()))
    print("Soil min/max:", round(df["Soil_Moisture"].min(), 2), round(df["Soil_Moisture"].max(), 2))
    print("Drip ON %:", round(df["Drip"].mean() * 100, 2))
    print("Mist ON %:", round(df["Mist"].mean() * 100, 2))
    print("Fan ON %:", round(df["Fan"].mean() * 100, 2))

    csv_path = "greenhouse_data.csv"
    df.to_csv(csv_path, index=False)
    print(f"\nData saved successfully to {csv_path}")
