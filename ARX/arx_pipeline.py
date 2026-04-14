from __future__ import annotations

import importlib.util
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.diagnostic import acorr_ljungbox


DEFAULT_INPUT_COLS = ["Temperature", "Humidity", "Light", "Drip", "Mist", "Fan"]
DEFAULT_OUTPUT_COL = "Soil_Moisture"
DEFAULT_REQUIRED_COLUMNS = [
    "Timestamp",
    DEFAULT_OUTPUT_COL,
    *DEFAULT_INPUT_COLS,
]


@dataclass(frozen=True)
class DataConfig:
    csv_path: Path = Path("greenhouse_data.csv")
    generator_script_path: Path = Path("data_generator.py")
    force_regenerate_from_script: bool = True
    auto_save_generated_csv: bool = True
    generated_days: int = 365
    generated_sampling_seconds: int = 300
    generated_seed: int = 42
    generated_start_date: str = "2025-01-01"


@dataclass(frozen=True)
class SplitConfig:
    train_ratio: float = 0.60
    val_ratio: float = 0.20

    @property
    def test_ratio(self) -> float:
        return 1.0 - self.train_ratio - self.val_ratio

    def validate(self) -> None:
        if not (0.0 < self.train_ratio < 1.0):
            raise ValueError("train_ratio must be in (0, 1)")
        if not (0.0 < self.val_ratio < 1.0):
            raise ValueError("val_ratio must be in (0, 1)")
        if not np.isclose(self.train_ratio + self.val_ratio + self.test_ratio, 1.0):
            raise ValueError("Split ratios must sum to 1.0")
        if self.test_ratio <= 0.0:
            raise ValueError("test_ratio must be positive")


@dataclass(frozen=True)
class ModelConfig:
    na: int = 2
    nb: int = 2
    nk: int = 1
    include_intercept: bool = False
    input_cols: tuple[str, ...] = tuple(DEFAULT_INPUT_COLS)
    output_col: str = DEFAULT_OUTPUT_COL
    simulation_clip: tuple[float, float] | None = None

    @property
    def param_names(self) -> list[str]:
        names = [f"a{lag}" for lag in range(1, self.na + 1)]
        for col in self.input_cols:
            for lag in range(1, self.nb + 1):
                names.append(f"b_{col}_{lag}")
        if self.include_intercept:
            names.append("intercept")
        return names


def validate_dataframe(df_in: pd.DataFrame, required_cols: list[str] | None = None) -> pd.DataFrame:
    required = required_cols or list(DEFAULT_REQUIRED_COLUMNS)
    missing = [col for col in required if col not in df_in.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    if "Timestamp" in df_in.columns:
        df_in = df_in.sort_values("Timestamp").reset_index(drop=True)
    return df_in


def load_existing_csv(csv_path: Path) -> pd.DataFrame:
    df_csv = pd.read_csv(csv_path, parse_dates=["Timestamp"])
    return validate_dataframe(df_csv)


def load_generator_module(script_path: Path):
    if not script_path.exists():
        raise FileNotFoundError(
            f"Cannot find {script_path}. Provide greenhouse_data.csv or keep data_generator.py in the project root."
        )
    spec = importlib.util.spec_from_file_location("project_data_generator", script_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module from {script_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_generator_from_script(script_path: Path):
    module = load_generator_module(script_path)
    if not hasattr(module, "generate_greenhouse_data"):
        raise AttributeError("data_generator.py does not expose generate_greenhouse_data()")
    return module.generate_greenhouse_data


def extract_true_params_from_module(module) -> dict[str, float] | None:
    if hasattr(module, "get_true_params"):
        params = module.get_true_params()
        if isinstance(params, dict):
            return dict(params)
    if hasattr(module, "TRUE_PARAMS") and isinstance(module.TRUE_PARAMS, dict):
        return dict(module.TRUE_PARAMS)
    return None


def load_or_generate_data(config: DataConfig) -> tuple[pd.DataFrame, dict[str, float] | None, str]:
    if config.csv_path.exists() and not config.force_regenerate_from_script:
        df_loaded = load_existing_csv(config.csv_path)
        true_params = None
        if config.generator_script_path.exists():
            module = load_generator_module(config.generator_script_path)
            true_params = extract_true_params_from_module(module)
        return df_loaded, true_params, f"CSV:{config.csv_path.name}"

    generator = load_generator_from_script(config.generator_script_path)
    df_generated, true_params = generator(
        days=config.generated_days,
        T_s=config.generated_sampling_seconds,
        seed=config.generated_seed,
        start_date=config.generated_start_date,
    )
    df_generated = validate_dataframe(df_generated)
    if config.auto_save_generated_csv:
        df_generated.to_csv(config.csv_path, index=False)
    return df_generated, true_params, f"GENERATED:{config.generator_script_path.name}"


def split_time_series(
    df: pd.DataFrame,
    split_config: SplitConfig,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    split_config.validate()
    n_total = len(df)
    n_train = int(n_total * split_config.train_ratio)
    n_val = int(n_total * split_config.val_ratio)
    n_test_start = n_train + n_val
    df_train = df.iloc[:n_train].copy().reset_index(drop=True)
    df_val = df.iloc[n_train:n_test_start].copy().reset_index(drop=True)
    df_test = df.iloc[n_test_start:].copy().reset_index(drop=True)
    return df_train, df_val, df_test


def summarize_dataset_behavior(df_in: pd.DataFrame, label: str) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "label": label,
        "rows": int(len(df_in)),
    }

    if len(df_in) > 0 and "Timestamp" in df_in.columns:
        summary["timestamp_start"] = str(df_in["Timestamp"].iloc[0])
        summary["timestamp_end"] = str(df_in["Timestamp"].iloc[-1])

    if "Month" in df_in.columns:
        summary["months_present"] = sorted(int(v) for v in pd.Series(df_in["Month"]).dropna().unique())
    if "Season" in df_in.columns:
        summary["seasons_present"] = sorted(str(v) for v in pd.Series(df_in["Season"]).dropna().unique())

    for col in ["Drip", "Mist", "Fan"]:
        values = df_in[col].astype(float).to_numpy()
        on_pct = 100.0 * float(values.mean()) if len(values) else 0.0
        switch_count = int(np.abs(np.diff(values)).sum()) if len(values) > 1 else 0
        summary[f"{col.lower()}_on_pct"] = round(on_pct, 2)
        summary[f"{col.lower()}_switches"] = switch_count

    if {"Soil_Low_SP", "Soil_High_SP"}.issubset(df_in.columns):
        y = df_in["Soil_Moisture"].astype(float).to_numpy()
        lo = df_in["Soil_Low_SP"].astype(float).to_numpy()
        hi = df_in["Soil_High_SP"].astype(float).to_numpy()
        summary["below_sp_pct"] = round(100.0 * float(np.mean(y < lo)), 2)
        summary["inside_sp_pct"] = round(100.0 * float(np.mean((y >= lo) & (y <= hi))), 2)
        summary["above_sp_pct"] = round(100.0 * float(np.mean(y > hi)), 2)

    return summary


def build_regression_matrix(
    df: pd.DataFrame,
    model_config: ModelConfig,
) -> tuple[np.ndarray, np.ndarray]:
    y = df[model_config.output_col].astype(float).to_numpy()
    inputs = [df[col].astype(float).to_numpy() for col in model_config.input_cols]

    max_lag = max(model_config.na, model_config.nb + model_config.nk - 1)
    n_eff = len(y) - max_lag
    if n_eff <= 0:
        raise ValueError("Not enough rows for the configured lags")

    n_params = len(model_config.param_names)
    x_mat = np.zeros((n_eff, n_params), dtype=float)
    y_vec = np.zeros(n_eff, dtype=float)

    for row_idx in range(n_eff):
        t = row_idx + max_lag
        row: list[float] = []
        for lag in range(1, model_config.na + 1):
            row.append(float(y[t - lag]))
        for u in inputs:
            for lag in range(model_config.nk, model_config.nk + model_config.nb):
                row.append(float(u[t - lag]))
        if model_config.include_intercept:
            row.append(1.0)
        x_mat[row_idx] = row
        y_vec[row_idx] = float(y[t])

    return x_mat, y_vec


def estimate_ols(x_mat: np.ndarray, y_vec: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
    theta, _, _, _ = np.linalg.lstsq(x_mat, y_vec, rcond=None)
    n_obs, n_params = x_mat.shape
    resid = y_vec - x_mat @ theta
    sigma2 = float(np.dot(resid, resid) / max(1, (n_obs - n_params)))
    cov = sigma2 * np.linalg.pinv(x_mat.T @ x_mat)
    return theta, cov, sigma2


def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray, n_params: int) -> dict[str, float]:
    resid = np.asarray(y_true, dtype=float) - np.asarray(y_pred, dtype=float)
    n_obs = len(resid)
    ss_res = float(np.dot(resid, resid))
    ss_tot = float(np.dot(y_true - y_true.mean(), y_true - y_true.mean()))
    sigma2 = ss_res / max(1, n_obs)
    rmse = float(np.sqrt(sigma2))
    mae = float(np.mean(np.abs(resid)))
    bias = float(np.mean(resid))
    fit = float(100.0 * (1.0 - np.linalg.norm(resid) / np.linalg.norm(y_true - y_true.mean())))
    r2 = float(1.0 - ss_res / ss_tot) if ss_tot > 0 else float("nan")
    aic = float(n_obs * np.log(sigma2 + 1e-12) + 2 * n_params)
    bic = float(n_obs * np.log(sigma2 + 1e-12) + n_params * np.log(max(1, n_obs)))
    return {
        "RMSE": rmse,
        "MAE": mae,
        "Bias": bias,
        "FIT": fit,
        "R2": r2,
        "AIC": aic,
        "BIC": bic,
    }


def simulate_arx(
    df_sim: pd.DataFrame,
    theta: np.ndarray,
    model_config: ModelConfig,
) -> tuple[np.ndarray, np.ndarray]:
    y = df_sim[model_config.output_col].astype(float).to_numpy().copy()
    inputs = [df_sim[col].astype(float).to_numpy() for col in model_config.input_cols]
    max_lag = max(model_config.na, model_config.nb + model_config.nk - 1)
    y_sim = y.copy()

    for t in range(max_lag, len(y)):
        row: list[float] = []
        for lag in range(1, model_config.na + 1):
            row.append(float(y_sim[t - lag]))
        for u in inputs:
            for lag in range(model_config.nk, model_config.nk + model_config.nb):
                row.append(float(u[t - lag]))
        if model_config.include_intercept:
            row.append(1.0)
        y_next = float(np.dot(row, theta))
        if model_config.simulation_clip is not None:
            y_next = float(np.clip(y_next, model_config.simulation_clip[0], model_config.simulation_clip[1]))
        y_sim[t] = y_next

    return y_sim[max_lag:], y[max_lag:]


def simulate_arx_n_step(
    df_sim: pd.DataFrame,
    theta: np.ndarray,
    n_steps: int,
    model_config: ModelConfig,
) -> tuple[np.ndarray, np.ndarray]:
    y = df_sim[model_config.output_col].astype(float).to_numpy().copy()
    inputs = [df_sim[col].astype(float).to_numpy() for col in model_config.input_cols]
    max_lag = max(model_config.na, model_config.nb + model_config.nk - 1)
    y_sim = y.copy()

    for t in range(max_lag, len(y)):
        origin = max(max_lag - 1, t - n_steps)
        y_hist = y[origin - max_lag + 1 : origin + 1].copy()
        predicted_t = float("nan")
        for step_t in range(origin + 1, t + 1):
            row: list[float] = []
            for lag in range(1, model_config.na + 1):
                row.append(float(y_hist[-lag]))
            for u in inputs:
                for lag in range(model_config.nk, model_config.nk + model_config.nb):
                    row.append(float(u[step_t - lag]))
            if model_config.include_intercept:
                row.append(1.0)
            y_next = float(np.dot(row, theta))
            if model_config.simulation_clip is not None:
                y_next = float(np.clip(y_next, model_config.simulation_clip[0], model_config.simulation_clip[1]))
            y_hist = np.append(y_hist[1:], y_next)
            if step_t == t:
                predicted_t = y_next
        y_sim[t] = predicted_t

    return y_sim[max_lag:], y[max_lag:]


def parameter_reference_map(true_params: dict[str, float] | None) -> dict[str, float]:
    if true_params is None:
        return {}
    return {
        "a1": true_params.get("a1", np.nan),
        "a2": true_params.get("a2", np.nan),
        "b_Temperature_1": true_params.get("b_temp_1", np.nan),
        "b_Temperature_2": true_params.get("b_temp_2", np.nan),
        "b_Humidity_1": true_params.get("b_humi_1", np.nan),
        "b_Humidity_2": true_params.get("b_humi_2", np.nan),
        "b_Light_1": true_params.get("b_light_1", np.nan),
        "b_Light_2": true_params.get("b_light_2", np.nan),
        "b_Drip_1": true_params.get("b_drip_1", np.nan),
        "b_Drip_2": true_params.get("b_drip_2", np.nan),
        "b_Mist_1": true_params.get("b_mist_1", np.nan),
        "b_Mist_2": true_params.get("b_mist_2", np.nan),
        "b_Fan_1": true_params.get("b_fan_1", np.nan),
        "b_Fan_2": true_params.get("b_fan_2", np.nan),
    }


def summarize_parameters(
    theta: np.ndarray,
    cov: np.ndarray,
    model_config: ModelConfig,
    true_params: dict[str, float] | None,
) -> list[dict[str, Any]]:
    std = np.sqrt(np.diag(cov))
    refs = parameter_reference_map(true_params)
    summary: list[dict[str, Any]] = []
    for idx, name in enumerate(model_config.param_names):
        ref = refs.get(name, np.nan)
        est = float(theta[idx])
        std_i = float(std[idx])
        sign_ok = bool(np.sign(est) == np.sign(ref) or np.isnan(ref) or np.isclose(ref, 0.0))
        summary.append(
            {
                "name": name,
                "estimate": est,
                "std": std_i,
                "ci95_low": est - 1.96 * std_i,
                "ci95_high": est + 1.96 * std_i,
                "true_value": None if np.isnan(ref) else float(ref),
                "delta_vs_true": None if np.isnan(ref) else float(est - ref),
                "sign_ok": sign_ok,
            }
        )
    return summary


def compute_ar_roots(theta: np.ndarray, model_config: ModelConfig) -> list[dict[str, float]]:
    if model_config.na != 2:
        return []
    a1, a2 = float(theta[0]), float(theta[1])
    coeffs = np.array([1.0, -a1, -a2], dtype=float)
    roots = np.roots(coeffs)
    results: list[dict[str, float]] = []
    for idx, root in enumerate(roots, start=1):
        results.append(
            {
                "root_index": idx,
                "real": float(np.real(root)),
                "imag": float(np.imag(root)),
                "magnitude": float(np.abs(root)),
            }
        )
    return results


def residual_diagnostics(
    residuals: np.ndarray,
    df_slice: pd.DataFrame,
    model_config: ModelConfig,
    max_lag: int = 20,
) -> dict[str, Any]:
    residuals = np.asarray(residuals, dtype=float)
    diagnostics: dict[str, Any] = {
        "mean": float(np.mean(residuals)),
        "std": float(np.std(residuals, ddof=0)),
        "normality": {},
        "ljung_box": {},
        "input_cross_correlation": {},
    }

    shapiro_sample = residuals[: min(len(residuals), 5000)]
    shapiro_stat, shapiro_p = stats.shapiro(shapiro_sample)
    dagostino_stat, dagostino_p = stats.normaltest(residuals)
    diagnostics["normality"] = {
        "shapiro_stat": float(shapiro_stat),
        "shapiro_pvalue": float(shapiro_p),
        "dagostino_stat": float(dagostino_stat),
        "dagostino_pvalue": float(dagostino_p),
        "passes_shapiro": bool(shapiro_p > 0.05),
        "passes_dagostino": bool(dagostino_p > 0.05),
    }

    lb = acorr_ljungbox(residuals, lags=max_lag, return_df=True)
    failed_lags = [int(idx) for idx, row in lb.iterrows() if row["lb_pvalue"] < 0.05]
    diagnostics["ljung_box"] = {
        "max_lag": int(max_lag),
        "failed_lags": failed_lags,
        "passes_all_lags": len(failed_lags) == 0,
    }

    lag_offset = max(model_config.na, model_config.nb + model_config.nk - 1)
    n_min = min(len(residuals), len(df_slice) - lag_offset)
    for col in model_config.input_cols:
        u_vals = df_slice[col].astype(float).to_numpy()[lag_offset : lag_offset + n_min]
        cc = float(np.corrcoef(residuals[:n_min], u_vals[:n_min])[0, 1])
        diagnostics["input_cross_correlation"][col] = {
            "corr": cc,
            "passes_abs_lt_0_10": bool(abs(cc) < 0.10),
        }

    return diagnostics


def build_true_theta(true_params: dict[str, float] | None, model_config: ModelConfig) -> np.ndarray | None:
    refs = parameter_reference_map(true_params)
    if not refs:
        return None
    values = [refs[name] for name in model_config.param_names if name in refs]
    if len(values) != len(model_config.param_names):
        return None
    return np.asarray(values, dtype=float)


def evaluate_slice(
    name: str,
    df_slice: pd.DataFrame,
    theta: np.ndarray,
    model_config: ModelConfig,
    true_theta: np.ndarray | None = None,
    n_step: int = 12,
) -> dict[str, Any]:
    x_mat, y_vec = build_regression_matrix(df_slice, model_config)
    y_pred = x_mat @ theta
    y_sim, y_true_sim = simulate_arx(df_slice, theta, model_config)
    y_n_step, _ = simulate_arx_n_step(df_slice, theta, n_steps=n_step, model_config=model_config)

    result: dict[str, Any] = {
        "name": name,
        "metrics_1step": compute_metrics(y_vec, y_pred, len(theta)),
        "metrics_n_step": compute_metrics(y_true_sim, y_n_step, len(theta)),
        "metrics_sim": compute_metrics(y_true_sim, y_sim, len(theta)),
        "arrays": {
            "y_true_1step": y_vec,
            "y_pred_1step": y_pred,
            "y_true_sim": y_true_sim,
            "y_pred_sim": y_sim,
            "y_pred_n_step": y_n_step,
        },
        "residual_diagnostics": residual_diagnostics(y_vec - y_pred, df_slice, model_config),
        "behavior": summarize_dataset_behavior(df_slice, name),
    }

    if true_theta is not None:
        true_sim, _ = simulate_arx(df_slice, true_theta, model_config)
        result["theoretical_max_free_run"] = compute_metrics(y_true_sim, true_sim, len(true_theta))

    return result


def model_selection_search(
    df_train: pd.DataFrame,
    df_val: pd.DataFrame,
    base_model_config: ModelConfig,
    na_list: list[int],
    nb_list: list[int],
    nk_list: list[int],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for na in na_list:
        for nb in nb_list:
            for nk in nk_list:
                candidate = ModelConfig(
                    na=na,
                    nb=nb,
                    nk=nk,
                    include_intercept=base_model_config.include_intercept,
                    input_cols=base_model_config.input_cols,
                    output_col=base_model_config.output_col,
                    simulation_clip=base_model_config.simulation_clip,
                )
                try:
                    x_tr, y_tr = build_regression_matrix(df_train, candidate)
                    theta, _, _ = estimate_ols(x_tr, y_tr)
                    evaluation = evaluate_slice("Validation", df_val, theta, candidate, true_theta=None, n_step=12)
                except Exception as exc:
                    rows.append(
                        {
                            "na": na,
                            "nb": nb,
                            "nk": nk,
                            "error": str(exc),
                        }
                    )
                    continue

                metrics_1step = evaluation["metrics_1step"]
                metrics_sim = evaluation["metrics_sim"]
                rows.append(
                    {
                        "na": na,
                        "nb": nb,
                        "nk": nk,
                        "n_params": len(theta),
                        "RMSE_1step": metrics_1step["RMSE"],
                        "FIT_1step": metrics_1step["FIT"],
                        "R2_1step": metrics_1step["R2"],
                        "AIC_1step": metrics_1step["AIC"],
                        "BIC_1step": metrics_1step["BIC"],
                        "RMSE_sim": metrics_sim["RMSE"],
                        "FIT_sim": metrics_sim["FIT"],
                        "R2_sim": metrics_sim["R2"],
                    }
                )

    df_results = pd.DataFrame(rows)
    if "error" in df_results.columns:
        df_results = df_results[df_results["error"].isna()]
    return df_results.sort_values(
        ["RMSE_sim", "RMSE_1step", "AIC_1step", "n_params"],
        ascending=[True, True, True, True],
    ).reset_index(drop=True)


def evaluate_candidate_order(
    df_train: pd.DataFrame,
    df_val: pd.DataFrame,
    df_test: pd.DataFrame,
    base_model_config: ModelConfig,
    na: int,
    nb: int,
    nk: int,
) -> dict[str, Any]:
    candidate = ModelConfig(
        na=na,
        nb=nb,
        nk=nk,
        include_intercept=base_model_config.include_intercept,
        input_cols=base_model_config.input_cols,
        output_col=base_model_config.output_col,
        simulation_clip=base_model_config.simulation_clip,
    )
    x_train, y_train = build_regression_matrix(df_train, candidate)
    theta, cov, sigma2 = estimate_ols(x_train, y_train)
    return {
        "model_config": candidate,
        "theta_hat": theta.tolist(),
        "sigma2": float(sigma2),
        "val": evaluate_slice("Validation", df_val, theta, candidate, true_theta=None, n_step=12),
        "test": evaluate_slice("Test", df_test, theta, candidate, true_theta=None, n_step=12),
    }


def _json_ready(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, dict):
        return {key: _json_ready(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    return value


def artifact_payload(results: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "model": "ARX",
        "data_source": results["data_source"],
        "data_config": _json_ready(asdict(results["data_config"])),
        "split_config": _json_ready(asdict(results["split_config"])),
        "model_config": _json_ready(asdict(results["model_config"])),
        "dataset_overview": results["dataset_overview"],
        "param_names": results["model_config"].param_names,
        "theta_hat": results["theta_hat"],
        "sigma2": results["sigma2"],
        "ar_roots": results["ar_roots"],
        "parameter_summary": results["parameter_summary"],
        "slices": {},
        "model_selection_top10": results["model_selection"].head(10).to_dict(orient="records"),
        "true_params": results["true_params"],
    }

    for slice_name in ["train", "val", "test"]:
        evaluation = results[slice_name]
        payload["slices"][slice_name] = {
            "metrics_1step": evaluation["metrics_1step"],
            "metrics_n_step": evaluation["metrics_n_step"],
            "metrics_sim": evaluation["metrics_sim"],
            "behavior": evaluation["behavior"],
            "residual_diagnostics": evaluation["residual_diagnostics"],
            "theoretical_max_free_run": evaluation.get("theoretical_max_free_run"),
        }

    payload["summary"] = {
        "sign_ok_count": int(sum(1 for row in results["parameter_summary"] if row["sign_ok"])),
        "sign_total_count": int(len(results["parameter_summary"])),
        "baseline_order": {
            "na": results["model_config"].na,
            "nb": results["model_config"].nb,
            "nk": results["model_config"].nk,
        },
        "best_model_by_free_run": results["model_selection"].head(1).to_dict(orient="records"),
    }
    if "best_candidate" in results:
        payload["best_candidate"] = {
            "model_config": _json_ready(asdict(results["best_candidate"]["model_config"])),
            "theta_hat": results["best_candidate"]["theta_hat"],
            "sigma2": results["best_candidate"]["sigma2"],
            "val": {
                "metrics_1step": results["best_candidate"]["val"]["metrics_1step"],
                "metrics_n_step": results["best_candidate"]["val"]["metrics_n_step"],
                "metrics_sim": results["best_candidate"]["val"]["metrics_sim"],
            },
            "test": {
                "metrics_1step": results["best_candidate"]["test"]["metrics_1step"],
                "metrics_n_step": results["best_candidate"]["test"]["metrics_n_step"],
                "metrics_sim": results["best_candidate"]["test"]["metrics_sim"],
            },
        }
    return _json_ready(payload)


def run_pipeline(
    data_config: DataConfig | None = None,
    split_config: SplitConfig | None = None,
    model_config: ModelConfig | None = None,
) -> dict[str, Any]:
    data_cfg = data_config or DataConfig()
    split_cfg = split_config or SplitConfig()
    model_cfg = model_config or ModelConfig()

    df, true_params, data_source = load_or_generate_data(data_cfg)
    df_train, df_val, df_test = split_time_series(df, split_cfg)

    x_train, y_train = build_regression_matrix(df_train, model_cfg)
    theta_hat, cov_hat, sigma2_hat = estimate_ols(x_train, y_train)
    true_theta = build_true_theta(true_params, model_cfg)

    dataset_overview = {
        "rows": int(len(df)),
        "timestamp_start": str(df["Timestamp"].iloc[0]),
        "timestamp_end": str(df["Timestamp"].iloc[-1]),
        "months_present": sorted(int(v) for v in pd.Series(df["Month"]).dropna().unique()),
        "seasons_present": sorted(str(v) for v in pd.Series(df["Season"]).dropna().unique()),
        "condition_number_xtx": float(np.linalg.cond(x_train.T @ x_train)),
        "rank_x_train": int(np.linalg.matrix_rank(x_train)),
        "n_params": int(len(model_cfg.param_names)),
    }

    results = {
        "data_source": data_source,
        "data_config": data_cfg,
        "split_config": split_cfg,
        "model_config": model_cfg,
        "df_full": df,
        "df_train": df_train,
        "df_val": df_val,
        "df_test": df_test,
        "true_params": true_params,
        "dataset_overview": dataset_overview,
        "theta_hat": theta_hat.tolist(),
        "sigma2": float(sigma2_hat),
        "ar_roots": compute_ar_roots(theta_hat, model_cfg),
        "parameter_summary": summarize_parameters(theta_hat, cov_hat, model_cfg, true_params),
        "train": evaluate_slice("Train", df_train, theta_hat, model_cfg, true_theta=true_theta, n_step=12),
        "val": evaluate_slice("Validation", df_val, theta_hat, model_cfg, true_theta=true_theta, n_step=12),
        "test": evaluate_slice("Test", df_test, theta_hat, model_cfg, true_theta=true_theta, n_step=12),
        "model_selection": model_selection_search(
            df_train=df_train,
            df_val=df_val,
            base_model_config=model_cfg,
            na_list=[1, 2, 3],
            nb_list=[1, 2, 3],
            nk_list=[1, 2],
        ),
    }
    if not results["model_selection"].empty:
        best_row = results["model_selection"].iloc[0]
        results["best_candidate"] = evaluate_candidate_order(
            df_train=df_train,
            df_val=df_val,
            df_test=df_test,
            base_model_config=model_cfg,
            na=int(best_row["na"]),
            nb=int(best_row["nb"]),
            nk=int(best_row["nk"]),
        )
    return results


def print_cli_summary(results: dict[str, Any]) -> None:
    overview = results["dataset_overview"]
    print("=== Dataset ===")
    print(f"Source              : {results['data_source']}")
    print(f"Rows                : {overview['rows']}")
    print(f"Range               : {overview['timestamp_start']} -> {overview['timestamp_end']}")
    print(f"Months present      : {overview['months_present']}")
    print(f"Seasons present     : {overview['seasons_present']}")
    print(f"Rank(X_train)       : {overview['rank_x_train']} / {overview['n_params']}")
    print(f"Cond(X'X)           : {overview['condition_number_xtx']:.2f}")
    print()

    print("=== Metrics ===")
    print(f"{'Slice':<10} | {'1-step FIT':>10} | {'12-step FIT':>11} | {'Sim FIT':>9} | {'Theo Sim FIT':>12}")
    print("-" * 66)
    for key in ["train", "val", "test"]:
        evaluation = results[key]
        theo = evaluation.get("theoretical_max_free_run", {})
        theo_fit = theo.get("FIT", float("nan")) if theo else float("nan")
        print(
            f"{evaluation['name']:<10} | "
            f"{evaluation['metrics_1step']['FIT']:>10.3f} | "
            f"{evaluation['metrics_n_step']['FIT']:>11.3f} | "
            f"{evaluation['metrics_sim']['FIT']:>9.3f} | "
            f"{theo_fit:>12.3f}"
        )
    print()

    sign_ok_count = sum(1 for row in results["parameter_summary"] if row["sign_ok"])
    print("=== Parameters ===")
    print(f"Sign-correct params : {sign_ok_count} / {len(results['parameter_summary'])}")
    for row in results["parameter_summary"]:
        true_value = row["true_value"]
        true_display = "n/a" if true_value is None else f"{true_value:+.6f}"
        print(
            f"{row['name']:<18} est={row['estimate']:+.6f} "
            f"true={true_display:>10} sign_ok={str(row['sign_ok']):>5}"
        )
    print()

    print("=== Residual Diagnostics (Validation) ===")
    diag = results["val"]["residual_diagnostics"]
    print(f"Ljung-Box pass      : {diag['ljung_box']['passes_all_lags']}")
    print(f"Failed lags         : {diag['ljung_box']['failed_lags']}")
    print(f"Shapiro p-value     : {diag['normality']['shapiro_pvalue']:.4f}")
    print(f"D'Agostino p-value  : {diag['normality']['dagostino_pvalue']:.4f}")
    print()

    if not results["model_selection"].empty:
        best = results["model_selection"].iloc[0]
        print("=== Model Selection ===")
        print(
            f"Best free-run model : ARX({int(best.na)}, {int(best.nb)}, {int(best.nk)}) "
            f"| FIT_sim={best.FIT_sim:.3f} | RMSE_sim={best.RMSE_sim:.4f}"
        )


def save_artifact(results: dict[str, Any], output_path: Path = Path("arx_model.json")) -> None:
    payload = artifact_payload(results)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")


def main() -> None:
    results = run_pipeline()
    save_artifact(results)
    print_cli_summary(results)
    print("\nSaved model artifact to arx_model.json")


if __name__ == "__main__":
    main()
