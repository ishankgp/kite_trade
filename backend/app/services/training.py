"""Expanded modelling utilities with multi-model and walk-forward support."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, List, Optional

import joblib
import numpy as np
import pandas as pd
from prophet import Prophet
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

try:
    from xgboost import XGBRegressor  # type: ignore
except ImportError:  # pragma: no cover
    XGBRegressor = None  # type: ignore

from ..database import get_connection


@dataclass
class WalkForwardWindow:
    fold: int
    train_start: datetime
    train_end: datetime
    test_start: datetime
    test_end: datetime
    rmse: float
    mae: float
    mape: Optional[float]


def load_price_frame(instrument_token: int, interval: str) -> pd.DataFrame:
    with get_connection() as conn:
        query = (
            "SELECT timestamp, open, high, low, close, volume FROM price_bars "
            "WHERE instrument_token = ? AND interval = ? ORDER BY timestamp"
        )
        df = pd.read_sql_query(query, conn, params=(instrument_token, interval))
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


def compute_rsi(series: pd.Series, window: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(window).mean()
    loss = -delta.clip(upper=0).rolling(window).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high_low = df["high"] - df["low"]
    high_close = (df["high"] - df["close"].shift()).abs()
    low_close = (df["low"] - df["close"].shift()).abs()
    true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return true_range.rolling(period).mean()


def engineer_features(
    df: pd.DataFrame, forecast_horizon: int, lookback_window: int
) -> pd.DataFrame:
    data = df.copy()
    data.sort_values("timestamp", inplace=True)
    data["return"] = data["close"].pct_change()
    data["sma_20"] = data["close"].rolling(20).mean()
    data["sma_50"] = data["close"].rolling(50).mean()
    data["sma_200"] = data["close"].rolling(200).mean()
    data["rsi"] = compute_rsi(data["close"], window=14)
    data["atr"] = compute_atr(data)

    for lag in [1, 2, 3, 5, 10, 20]:
        data[f"close_lag_{lag}"] = data["close"].shift(lag)
        data[f"volume_lag_{lag}"] = data["volume"].shift(lag)

    data["target"] = data["close"].shift(-forecast_horizon)
    data.dropna(inplace=True)
    return data


def split_walk_forward(
    data: pd.DataFrame,
    train_bars: int,
    test_bars: int,
    step_size: Optional[int] = None,
) -> Iterable[tuple[pd.DataFrame, pd.DataFrame]]:
    step = step_size or test_bars
    start = 0
    while True:
        train_start = start
        train_end = train_start + train_bars
        test_end = train_end + test_bars
        if test_end > len(data):
            break
        train_df = data.iloc[train_start:train_end]
        test_df = data.iloc[train_end:test_end]
        if train_df.empty or test_df.empty:
            break
        yield train_df, test_df
        start += step


def evaluate_predictions(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    mae = float(mean_absolute_error(y_true, y_pred))
    with np.errstate(divide="ignore", invalid="ignore"):
        ape = np.abs((y_true - y_pred) / y_true)
        ape = ape[np.isfinite(ape)]
        mape = float(np.mean(ape) * 100) if ape.size else float("nan")
    return {"rmse": rmse, "mae": mae, "mape": mape}


def train_random_forest(X_train, y_train) -> Pipeline:
    pipeline = Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            (
                "model",
                RandomForestRegressor(
                    n_estimators=200,
                    random_state=42,
                    n_jobs=-1,
                ),
            ),
        ]
    )
    pipeline.fit(X_train, y_train)
    return pipeline


def train_xgboost(X_train, y_train) -> Optional[Pipeline]:
    if XGBRegressor is None:
        return None
    model = XGBRegressor(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        tree_method="hist",
    )
    pipeline = Pipeline([("model", model)])
    pipeline.fit(X_train, y_train)
    return pipeline


def train_prophet(train_df: pd.DataFrame) -> Prophet:
    prophet_df = train_df[["timestamp", "close"]].rename(
        columns={"timestamp": "ds", "close": "y"}
    )
    model = Prophet()
    model.fit(prophet_df)
    return model


def forecast_prophet(model: Prophet, periods: int, freq: str) -> np.ndarray:
    future = model.make_future_dataframe(periods=periods, freq=freq)
    forecast = model.predict(future)
    return forecast["yhat"].tail(periods).to_numpy()


def save_model(model, instrument_token: int, interval: str, model_name: str) -> str:
    os.makedirs("models", exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    path = f"models/{instrument_token}_{interval}_{model_name}_{timestamp}.joblib"
    joblib.dump(model, path)
    return path


def run_training_job(
    instrument_token: int,
    interval: str,
    models: List[str],
    forecast_horizon: int,
    lookback_window: int,
    walkforward_train_bars: int,
    walkforward_test_bars: int,
    step_size: Optional[int] = None,
) -> Dict[str, Dict[str, object]]:
    df = load_price_frame(instrument_token, interval)
    if len(df) < walkforward_train_bars + walkforward_test_bars + 10:
        raise ValueError("Not enough history for requested walk-forward configuration")

    feature_df = engineer_features(df, forecast_horizon, lookback_window)
    feature_columns = [col for col in feature_df.columns if col not in {"timestamp", "target"}]

    X = feature_df[feature_columns]
    y = feature_df["target"]

    results: Dict[str, Dict[str, object]] = {}

    for model_name in models:
        start_time = time.time()
        fold_metrics: List[Dict[str, object]] = []
        artifacts: Optional[str] = None

        for fold_idx, (train_df, test_df) in enumerate(
            split_walk_forward(feature_df, walkforward_train_bars, walkforward_test_bars, step_size),
            start=1,
        ):
            X_train = train_df[feature_columns]
            y_train = train_df["target"]
            X_test = test_df[feature_columns]
            y_test = test_df["target"]

            if model_name == "random_forest":
                model = train_random_forest(X_train, y_train)
                preds = model.predict(X_test)
            elif model_name == "xgboost":
                model = train_xgboost(X_train, y_train)
                if model is None:
                    continue
                preds = model.predict(X_test)
            elif model_name == "prophet":
                prophet_model = train_prophet(train_df)
                freq = "T" if interval.endswith("minute") else "D"
                preds = forecast_prophet(prophet_model, len(test_df), freq)
                model = prophet_model
            else:
                continue

            metrics = evaluate_predictions(y_test.to_numpy(), preds)
            fold_metrics.append(
                {
                    "fold": fold_idx,
                    "train_start": train_df["timestamp"].iloc[0],
                    "train_end": train_df["timestamp"].iloc[-1],
                    "test_start": test_df["timestamp"].iloc[0],
                    "test_end": test_df["timestamp"].iloc[-1],
                    **metrics,
                }
            )

        if not fold_metrics:
            continue

        latest_model = model  # type: ignore
        artifacts = save_model(latest_model, instrument_token, interval, model_name)

        overall_rmse = float(np.mean([m["rmse"] for m in fold_metrics]))
        overall_mae = float(np.mean([m["mae"] for m in fold_metrics]))
        valid_mapes = [m["mape"] for m in fold_metrics if isinstance(m["mape"], (float, int)) and not np.isnan(m["mape"]) ]
        overall_mape = float(np.mean(valid_mapes)) if valid_mapes else float("nan")

        results[model_name] = {
            "metrics_overall": {
                "rmse": overall_rmse,
                "mae": overall_mae,
                "mape": overall_mape,
            },
            "walk_forward": fold_metrics,
            "artifact_path": artifacts,
            "training_time_seconds": time.time() - start_time,
        }

    return results


