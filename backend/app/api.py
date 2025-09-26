"""FastAPI application for @nifty_ml backend."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .database import get_connection, init_db
from .models import (
    Instrument,
    InstrumentListResponse,
    PriceBar,
    PriceBarsResponse,
    TrainingModelResult,
    TrainingRequest,
    TrainingRunResponse,
    WalkForwardMetric,
)
from .services.analytics import compute_summary, compute_technicals
from .services.training import run_training_job


def create_app() -> FastAPI:
    init_db()
    settings = get_settings()

    app = FastAPI(title=settings.app_name)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["system"])
    def health_check() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/instruments", response_model=InstrumentListResponse, tags=["instruments"])
    def list_instruments(
        segment: Optional[str] = Query(None),
        exchange: Optional[str] = Query(None),
        search: Optional[str] = Query(None, description="Substring to match tradingsymbol or name"),
        limit: int = Query(200, ge=1, le=1000),
        offset: int = Query(0, ge=0),
    ) -> InstrumentListResponse:
        query = "SELECT * FROM instruments"
        filters: list[str] = []
        params: list = []

        if segment:
            filters.append("segment = ?")
            params.append(segment)
        if exchange:
            filters.append("exchange = ?")
            params.append(exchange)
        if search:
            filters.append("(tradingsymbol LIKE ? OR name LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%"])

        if filters:
            query += " WHERE " + " AND ".join(filters)

        total_query = f"SELECT COUNT(*) FROM ({query})"
        query += " ORDER BY tradingsymbol LIMIT ? OFFSET ?"

        with get_connection() as conn:
            total = conn.execute(total_query, params).fetchone()[0]
            rows = conn.execute(query, params + [limit, offset]).fetchall()

        instruments = [Instrument(**dict(row)) for row in rows]
        return InstrumentListResponse(items=instruments, total=total)

    @app.get("/price-bars", response_model=PriceBarsResponse, tags=["prices"])
    def get_price_bars(
        instrument_token: int = Query(..., description="Instrument token to query"),
        interval: str = Query(..., description="Interval string such as 'minute', 'day'"),
        start: Optional[datetime] = Query(None, description="Inclusive start timestamp"),
        end: Optional[datetime] = Query(None, description="Inclusive end timestamp"),
        limit: int = Query(5000, ge=1, le=20000),
    ) -> PriceBarsResponse:
        with get_connection() as conn:
            instrument_row = conn.execute(
                "SELECT * FROM instruments WHERE instrument_token = ?", (instrument_token,)
            ).fetchone()
            if not instrument_row:
                raise HTTPException(status_code=404, detail="Instrument not found")

            query = "SELECT * FROM price_bars WHERE instrument_token = ? AND interval = ?"
            params: list = [instrument_token, interval]
            if start:
                query += " AND timestamp >= ?"
                params.append(start.isoformat())
            if end:
                query += " AND timestamp <= ?"
                params.append(end.isoformat())

            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            rows = conn.execute(query, params).fetchall()

        items = [PriceBar(**dict(row)) for row in rows]
        items.reverse()  # ascending chronological order for consumers
        return PriceBarsResponse(
            instrument_token=instrument_token,
            interval=interval,
            start=start,
            end=end,
            count=len(items),
            items=items,
        )

    return app


app = create_app()


@app.get("/analytics/summary", tags=["analytics"])
def analytics_summary(
    instrument_token: int = Query(...),
    interval: str = Query("day"),
):
    try:
        data = compute_summary(instrument_token, interval)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return data


@app.get("/analytics/technicals", tags=["analytics"])
def analytics_technicals(
    instrument_token: int = Query(...),
    interval: str = Query("day"),
):
    try:
        data = compute_technicals(instrument_token, interval)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return data


@app.post("/training/run", tags=["training"], response_model=TrainingRunResponse)
def run_training(request: TrainingRequest):
    try:
        results = run_training_job(
            instrument_token=request.instrument_token,
            interval=request.interval,
            models=request.models,
            forecast_horizon=request.forecast_horizon,
            lookback_window=request.lookback_window,
            walkforward_train_bars=request.walkforward_train_bars,
            walkforward_test_bars=request.walkforward_test_bars,
            step_size=request.step_size,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    model_results = [
        TrainingModelResult(
            model_name=name,
            metrics_overall=data["metrics_overall"],
            walk_forward=[
                WalkForwardMetric(
                    fold=fold["fold"],
                    train_start=fold["train_start"],
                    train_end=fold["train_end"],
                    test_start=fold["test_start"],
                    test_end=fold["test_end"],
                    rmse=fold["rmse"],
                    mae=fold["mae"],
                    mape=None if isinstance(fold["mape"], float) and np.isnan(fold["mape"]) else fold["mape"],
                )
                for fold in data["walk_forward"]
            ],
            artifact_path=data["artifact_path"],
            training_time_seconds=data["training_time_seconds"],
        )
        for name, data in results.items()
    ]

    return TrainingRunResponse(
        instrument_token=request.instrument_token,
        interval=request.interval,
        forecast_horizon=request.forecast_horizon,
        models=model_results,
    )


