"""Pydantic models for API serialization."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel


class Instrument(BaseModel):
    instrument_token: int
    tradingsymbol: Optional[str]
    name: Optional[str]
    segment: Optional[str]
    exchange: Optional[str]
    lot_size: Optional[int]
    expiry: Optional[str]
    last_refreshed: Optional[str]


class PriceBar(BaseModel):
    instrument_token: int
    interval: str
    timestamp: datetime
    open: Optional[float]
    high: Optional[float]
    low: Optional[float]
    close: Optional[float]
    volume: Optional[float]
    oi: Optional[float]


class InstrumentListResponse(BaseModel):
    items: list[Instrument]
    total: int


class PriceBarsResponse(BaseModel):
    instrument_token: int
    interval: str
    start: Optional[datetime]
    end: Optional[datetime]
    count: int
    items: list[PriceBar]


class WalkForwardMetric(BaseModel):
    fold: int
    train_start: datetime
    train_end: datetime
    test_start: datetime
    test_end: datetime
    rmse: float
    mae: float
    mape: Optional[float]


class TrainingRequest(BaseModel):
    instrument_token: int
    interval: str
    models: List[str] = ["random_forest", "xgboost"]
    forecast_horizon: int = 1
    lookback_window: int = 20
    walkforward_train_bars: int = 300
    walkforward_test_bars: int = 60
    step_size: Optional[int] = None


class TrainingModelResult(BaseModel):
    model_name: str
    metrics_overall: Dict[str, float]
    walk_forward: List[WalkForwardMetric]
    artifact_path: Optional[str]
    training_time_seconds: float


class TrainingRunResponse(BaseModel):
    instrument_token: int
    interval: str
    forecast_horizon: int
    models: List[TrainingModelResult]



