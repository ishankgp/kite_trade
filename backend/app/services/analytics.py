"""Analytical utilities for instruments."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from statistics import mean
from typing import Dict, List, Optional

from ..database import get_connection


@dataclass
class Bar:
    timestamp: datetime
    open: Optional[float]
    high: Optional[float]
    low: Optional[float]
    close: Optional[float]
    volume: Optional[float]


def _fetch_recent_bars(
    instrument_token: int,
    interval: str,
    limit: int,
) -> List[Bar]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT timestamp, open, high, low, close, volume
            FROM price_bars
            WHERE instrument_token = ? AND interval = ?
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (instrument_token, interval, limit),
        ).fetchall()

    bars: List[Bar] = []
    for row in rows:
        bars.append(
            Bar(
                timestamp=datetime.fromisoformat(row["timestamp"]),
                open=row["open"],
                high=row["high"],
                low=row["low"],
                close=row["close"],
                volume=row["volume"],
            )
        )

    bars.reverse()  # chronological order
    return bars


def compute_summary(
    instrument_token: int,
    interval: str,
) -> Dict[str, Optional[float]]:
    bars = _fetch_recent_bars(instrument_token, interval, limit=120)
    if len(bars) < 2:
        raise ValueError("Not enough price bars to compute summary")

    latest = bars[-1]
    previous = bars[-2]

    last_close = latest.close
    prev_close = previous.close
    if last_close is None or prev_close is None:
        change = None
        change_pct = None
    else:
        change = last_close - prev_close
        change_pct = (change / prev_close) * 100 if prev_close else None

    volumes = [bar.volume for bar in bars[-20:] if bar.volume is not None]
    average_volume = mean(volumes) if volumes else None

    return {
        "instrument_token": instrument_token,
        "interval": interval,
        "as_of": latest.timestamp,
        "last_close": last_close,
        "previous_close": prev_close,
        "change": change,
        "change_pct": change_pct,
        "average_volume": average_volume,
    }


def compute_moving_average(bars: List[Bar], window: int) -> Optional[float]:
    closes = [bar.close for bar in bars if bar.close is not None]
    if len(closes) < window:
        return None
    return mean(closes[-window:])


def compute_rsi(bars: List[Bar], period: int = 14) -> Optional[float]:
    closes = [bar.close for bar in bars if bar.close is not None]
    if len(closes) < period + 1:
        return None

    gains: List[float] = []
    losses: List[float] = []
    for i in range(1, period + 1):
        change = closes[-i] - closes[-i - 1]
        if change >= 0:
            gains.append(change)
        else:
            losses.append(abs(change))

    avg_gain = mean(gains) if gains else 0.0
    avg_loss = mean(losses) if losses else 0.0
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss if avg_loss else 0.0
    return 100 - (100 / (1 + rs))


def compute_atr(bars: List[Bar], period: int = 14) -> Optional[float]:
    if len(bars) < period + 1:
        return None

    trs: List[float] = []
    for idx in range(-period, 0):
        current = bars[idx]
        prev = bars[idx - 1]
        if None in (current.high, current.low, prev.close):
            continue
        high = current.high
        low = current.low
        prev_close = prev.close
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))  # type: ignore
        trs.append(tr)

    if not trs:
        return None
    return mean(trs)


def compute_technicals(
    instrument_token: int,
    interval: str,
) -> Dict[str, Optional[float]]:
    bars = _fetch_recent_bars(instrument_token, interval, limit=300)
    if len(bars) < 2:
        raise ValueError("Not enough price bars to compute technicals")

    moving_averages = {
        "sma_20": compute_moving_average(bars, 20),
        "sma_50": compute_moving_average(bars, 50),
        "sma_200": compute_moving_average(bars, 200),
    }

    rsi = compute_rsi(bars, period=14)
    atr = compute_atr(bars, period=14)
    latest = bars[-1]

    return {
        "instrument_token": instrument_token,
        "interval": interval,
        "as_of": latest.timestamp,
        "moving_averages": moving_averages,
        "rsi": rsi,
        "atr": atr,
    }


