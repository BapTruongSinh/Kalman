from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from arx_pipeline import build_regression_matrix, compute_metrics


def max_lag(results: dict[str, Any]) -> int:
    model_config = results["model_config"]
    return max(model_config.na, model_config.nb + model_config.nk - 1)


def prediction_frame_for_split(results: dict[str, Any], split_key: str) -> pd.DataFrame:
    evaluation = results[split_key]
    df_slice = results[f"df_{split_key}"].copy().reset_index(drop=True)
    lag = max_lag(results)
    arrays = evaluation["arrays"]

    frame = df_slice.iloc[lag:].copy().reset_index(drop=True)
    frame["split"] = evaluation["name"]
    frame["y_true"] = arrays["y_true_1step"]
    frame["y_pred_1step"] = arrays["y_pred_1step"]
    frame["y_pred_12step"] = arrays["y_pred_n_step"]
    frame["y_pred_sim"] = arrays["y_pred_sim"]
    frame["residual_1step"] = frame["y_true"] - frame["y_pred_1step"]
    frame["residual_12step"] = frame["y_true"] - frame["y_pred_12step"]
    frame["residual_sim"] = frame["y_true"] - frame["y_pred_sim"]
    return frame


def combined_prediction_frame(results: dict[str, Any]) -> pd.DataFrame:
    frames = [prediction_frame_for_split(results, split_key) for split_key in ["train", "val", "test"]]
    return pd.concat(frames, axis=0, ignore_index=True)


def parameter_frame(results: dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame(results["parameter_summary"])


def standardized_parameter_frame(results: dict[str, Any], split_key: str = "train") -> pd.DataFrame:
    df_slice = results[f"df_{split_key}"]
    model_config = results["model_config"]
    x_mat, y_vec = build_regression_matrix(df_slice, model_config)
    theta = np.asarray(results["theta_hat"], dtype=float)
    x_std = x_mat.std(axis=0, ddof=0)
    y_std = float(y_vec.std(ddof=0))
    beta = np.divide(theta * x_std, y_std, out=np.zeros_like(theta), where=y_std > 0)
    return pd.DataFrame(
        {
            "name": model_config.param_names,
            "theta": theta,
            "x_std": x_std,
            "standardized_beta": beta,
            "abs_standardized_beta": np.abs(beta),
        }
    )


def behavior_frame(results: dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame([results["train"]["behavior"], results["val"]["behavior"], results["test"]["behavior"]])


def monthly_signal_summary(df: pd.DataFrame) -> pd.DataFrame:
    summary = (
        df.groupby("Month")
        .agg(
            soil_mean=("Soil_Moisture", "mean"),
            soil_std=("Soil_Moisture", "std"),
            temp_mean=("Temperature", "mean"),
            humi_mean=("Humidity", "mean"),
            light_mean=("Light", "mean"),
        )
        .reset_index()
    )
    return summary


def monthly_actuator_summary(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for month, df_month in df.groupby("Month"):
        row: dict[str, Any] = {"Month": int(month)}
        for col in ["Drip", "Mist", "Fan"]:
            values = df_month[col].astype(float).to_numpy()
            row[f"{col.lower()}_on_pct"] = 100.0 * float(values.mean()) if len(values) else 0.0
            row[f"{col.lower()}_switches"] = int(np.abs(np.diff(values)).sum()) if len(values) > 1 else 0
        rows.append(row)
    return pd.DataFrame(rows).sort_values("Month").reset_index(drop=True)


def monthly_setpoint_summary(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for month, df_month in df.groupby("Month"):
        y = df_month["Soil_Moisture"].astype(float).to_numpy()
        lo = df_month["Soil_Low_SP"].astype(float).to_numpy()
        hi = df_month["Soil_High_SP"].astype(float).to_numpy()
        rows.append(
            {
                "Month": int(month),
                "below_sp_pct": 100.0 * float(np.mean(y < lo)),
                "inside_sp_pct": 100.0 * float(np.mean((y >= lo) & (y <= hi))),
                "above_sp_pct": 100.0 * float(np.mean(y > hi)),
            }
        )
    return pd.DataFrame(rows).sort_values("Month").reset_index(drop=True)


def rolling_rmse(y_true: pd.Series | np.ndarray, y_pred: pd.Series | np.ndarray, window: int) -> pd.Series:
    y_true_s = pd.Series(np.asarray(y_true, dtype=float))
    y_pred_s = pd.Series(np.asarray(y_pred, dtype=float))
    sq_err = (y_true_s - y_pred_s) ** 2
    return sq_err.rolling(window=window, min_periods=max(5, window // 10)).mean().pow(0.5)


def contribution_frame(results: dict[str, Any], split_key: str = "train") -> pd.DataFrame:
    df_slice = results[f"df_{split_key}"]
    model_config = results["model_config"]
    x_mat, _ = build_regression_matrix(df_slice, model_config)
    theta = np.asarray(results["theta_hat"], dtype=float)
    contribution_mat = x_mat * theta[np.newaxis, :]
    mean_abs = np.mean(np.abs(contribution_mat), axis=0)
    total_mean_abs = float(np.sum(mean_abs))
    share = np.divide(mean_abs, total_mean_abs, out=np.zeros_like(mean_abs), where=total_mean_abs > 0)
    return pd.DataFrame(
        {
            "name": model_config.param_names,
            "mean_signed_contribution": np.mean(contribution_mat, axis=0),
            "mean_abs_contribution": mean_abs,
            "contribution_share": share,
        }
    )


def impulse_response_frame(
    results: dict[str, Any],
    split_key: str = "train",
    horizon: int = 48,
    pulse_mode: str = "std",
) -> pd.DataFrame:
    df_slice = results[f"df_{split_key}"]
    model_config = results["model_config"]
    theta = np.asarray(results["theta_hat"], dtype=float)
    na = model_config.na
    nb = model_config.nb
    nk = model_config.nk
    input_cols = list(model_config.input_cols)

    input_scales: dict[str, float] = {}
    for col in input_cols:
        if pulse_mode == "std":
            input_scales[col] = float(df_slice[col].astype(float).std(ddof=0))
        elif pulse_mode == "unit":
            input_scales[col] = 1.0
        else:
            raise ValueError("pulse_mode must be 'std' or 'unit'")

    theta_idx = na
    input_coeffs: dict[str, np.ndarray] = {}
    for col in input_cols:
        input_coeffs[col] = theta[theta_idx : theta_idx + nb]
        theta_idx += nb

    rows: list[dict[str, Any]] = []
    for col in input_cols:
        pulse_size = input_scales[col]
        y_resp = np.zeros(horizon + 1, dtype=float)
        u_resp = {name: np.zeros(horizon + 1, dtype=float) for name in input_cols}
        u_resp[col][0] = pulse_size

        for t in range(horizon + 1):
            y_next = 0.0
            for lag in range(1, na + 1):
                if t - lag >= 0:
                    y_next += theta[lag - 1] * y_resp[t - lag]
            for input_name in input_cols:
                coeffs = input_coeffs[input_name]
                for lag in range(nk, nk + nb):
                    if t - lag >= 0:
                        y_next += coeffs[lag - nk] * u_resp[input_name][t - lag]
            y_resp[t] = y_next

        cumulative = np.cumsum(y_resp)
        for step in range(horizon + 1):
            rows.append(
                {
                    "input": col,
                    "step": step,
                    "pulse_mode": pulse_mode,
                    "pulse_size": pulse_size,
                    "response": y_resp[step],
                    "cumulative_response": cumulative[step],
                }
            )

    return pd.DataFrame(rows)


def grouped_metrics(
    prediction_df: pd.DataFrame,
    group_cols: list[str],
    modes: dict[str, str] | None = None,
) -> pd.DataFrame:
    use_modes = modes or {
        "1-step": "y_pred_1step",
        "12-step": "y_pred_12step",
        "free-run": "y_pred_sim",
    }
    rows: list[dict[str, Any]] = []
    for group_keys, df_group in prediction_df.groupby(group_cols):
        if not isinstance(group_keys, tuple):
            group_keys = (group_keys,)
        group_payload = {col: value for col, value in zip(group_cols, group_keys)}
        y_true = df_group["y_true"].to_numpy(dtype=float)
        for mode_name, pred_col in use_modes.items():
            metrics = compute_metrics(y_true, df_group[pred_col].to_numpy(dtype=float), n_params=0)
            row = dict(group_payload)
            row["mode"] = mode_name
            row.update(metrics)
            rows.append(row)
    return pd.DataFrame(rows)


def model_comparison_frame(results: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    baseline = {
        "label": f"Baseline ARX({results['model_config'].na},{results['model_config'].nb},{results['model_config'].nk})",
        "val": results["val"],
        "test": results["test"],
    }
    candidates = [baseline]
    if "best_candidate" in results:
        best_cfg = results["best_candidate"]["model_config"]
        candidates.append(
            {
                "label": f"Best free-run ARX({best_cfg.na},{best_cfg.nb},{best_cfg.nk})",
                "val": results["best_candidate"]["val"],
                "test": results["best_candidate"]["test"],
            }
        )

    for candidate in candidates:
        for split_key in ["val", "test"]:
            evaluation = candidate[split_key]
            rows.append(
                {
                    "model": candidate["label"],
                    "split": evaluation["name"],
                    "FIT_1step": evaluation["metrics_1step"]["FIT"],
                    "FIT_12step": evaluation["metrics_n_step"]["FIT"],
                    "FIT_sim": evaluation["metrics_sim"]["FIT"],
                    "RMSE_1step": evaluation["metrics_1step"]["RMSE"],
                    "RMSE_sim": evaluation["metrics_sim"]["RMSE"],
                }
            )
    return pd.DataFrame(rows)


def selection_metric_grid(selection_df: pd.DataFrame, metric: str, nk: int) -> pd.DataFrame:
    subset = selection_df[selection_df["nk"] == nk].copy()
    return subset.pivot(index="na", columns="nb", values=metric).sort_index().sort_index(axis=1)
