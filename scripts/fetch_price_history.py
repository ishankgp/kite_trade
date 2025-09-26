#!/usr/bin/env python3
"""Fetch historical price data and persist it into a local SQLite database.

Usage example (fetch last year of NIFTY 50 daily data):

    python scripts/fetch_price_history.py

Provide additional instruments by repeating the --instrument flag.
"""

from __future__ import annotations

import argparse
import logging
import os
import sqlite3
import sys
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.append(ROOT)

from env_loader import get_kite_config
from kite_token_manager import KiteTokenManager


logger = logging.getLogger(__name__)


def init_db(db_path: str) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS instruments (
            instrument_token INTEGER PRIMARY KEY,
            tradingsymbol TEXT,
            name TEXT,
            segment TEXT,
            exchange TEXT,
            lot_size INTEGER,
            expiry TEXT,
            last_refreshed TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS price_bars (
            instrument_token INTEGER NOT NULL,
            interval TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume REAL,
            oi REAL,
            PRIMARY KEY (instrument_token, interval, timestamp),
            FOREIGN KEY (instrument_token) REFERENCES instruments(instrument_token)
        )
        """
    )
    return conn


def upsert_instrument(conn: sqlite3.Connection, instrument: Dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO instruments (
            instrument_token, tradingsymbol, name, segment, exchange, lot_size, expiry, last_refreshed
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(instrument_token) DO UPDATE SET
            tradingsymbol=excluded.tradingsymbol,
            name=excluded.name,
            segment=excluded.segment,
            exchange=excluded.exchange,
            lot_size=excluded.lot_size,
            expiry=excluded.expiry,
            last_refreshed=excluded.last_refreshed
        """,
        (
            instrument["instrument_token"],
            instrument.get("tradingsymbol"),
            instrument.get("name"),
            instrument.get("segment"),
            instrument.get("exchange"),
            instrument.get("lot_size"),
            instrument.get("expiry"),
            datetime.utcnow().isoformat(),
        ),
    )


def upsert_price_bars(
    conn: sqlite3.Connection,
    instrument_token: int,
    interval: str,
    rows: Iterable[Dict[str, Any]],
) -> int:
    payload: List[tuple] = []
    for row in rows:
        timestamp = row.get("date")
        if isinstance(timestamp, datetime):
            timestamp_iso = timestamp.isoformat()
        else:
            timestamp_iso = str(timestamp)
        payload.append(
            (
                instrument_token,
                interval,
                timestamp_iso,
                row.get("open"),
                row.get("high"),
                row.get("low"),
                row.get("close"),
                row.get("volume"),
                row.get("oi"),
            )
        )

    if not payload:
        return 0

    conn.executemany(
        """
        INSERT INTO price_bars (
            instrument_token, interval, timestamp, open, high, low, close, volume, oi
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(instrument_token, interval, timestamp) DO UPDATE SET
            open=excluded.open,
            high=excluded.high,
            low=excluded.low,
            close=excluded.close,
            volume=excluded.volume,
            oi=excluded.oi
        """,
        payload,
    )
    return len(payload)


def resolve_instrument(
    catalogue: List[Dict[str, Any]],
    identifier: str,
    segment: Optional[str],
    exchange: Optional[str],
) -> Dict[str, Any]:
    identifier_upper = identifier.upper()
    matches = []
    for item in catalogue:
        tradingsymbol = str(item.get("tradingsymbol", "")).upper()
        name = str(item.get("name", "")).upper()
        if identifier_upper not in {tradingsymbol, name}:
            continue
        if segment and item.get("segment") != segment:
            continue
        if exchange and item.get("exchange") not in (None, "", exchange):
            continue
        matches.append(item)

    if not matches:
        raise ValueError(
            f"Instrument '{identifier}' not found. Try specifying --segment/--exchange "
            "or provide the instrument token directly."
        )

    if len(matches) > 1:
        logger.warning(
            "Multiple matches found for %s; selecting the first one: %s",
            identifier,
            matches[0],
        )
    return matches[0]


def resolve_chunk_days(interval: str, override: Optional[int]) -> int:
    if override is not None and override > 0:
        return override

    interval = interval.lower()
    defaults = {
        "minute": 30,
        "3minute": 60,
        "5minute": 90,
        "10minute": 120,
        "15minute": 150,
        "day": 365,
    }
    return defaults.get(interval, 120)


def historical_data_chunked(
    kite,
    instrument_token: int,
    interval: str,
    from_date: datetime,
    to_date: datetime,
    chunk_days: int,
):
    results: List[Dict[str, Any]] = []
    current_start = from_date
    delta = timedelta(days=chunk_days)

    while current_start < to_date:
        current_end = min(current_start + delta, to_date)
        logger.debug(
            "Requesting %s to %s (%s)", current_start.isoformat(), current_end.isoformat(), interval
        )
        batch = kite.historical_data(
            instrument_token=instrument_token,
            from_date=current_start,
            to_date=current_end,
            interval=interval,
            continuous=False,
            oi=True,
        )
        results.extend(batch)
        if current_end == to_date:
            break
        # Move start forward by one minute to avoid duplicate candles on boundary
        current_start = current_end + timedelta(minutes=1)
    return results


def fetch_and_store(
    kite,
    conn: sqlite3.Connection,
    instrument: Dict[str, Any],
    interval: str,
    lookback_days: int,
    chunk_days: int,
) -> None:
    instrument_token = int(instrument["instrument_token"])
    to_date = datetime.utcnow()
    from_date = to_date - timedelta(days=lookback_days)

    logger.info(
        "Fetching %s days of %s (%s) data from %s to %s",
        lookback_days,
        instrument.get("tradingsymbol") or instrument.get("name"),
        interval,
        from_date.date(),
        to_date.date(),
    )

    bars = historical_data_chunked(
        kite,
        instrument_token=instrument_token,
        interval=interval,
        from_date=from_date,
        to_date=to_date,
        chunk_days=chunk_days,
    )

    upsert_instrument(conn, instrument)
    count = upsert_price_bars(conn, instrument_token, interval, bars)
    conn.commit()
    logger.info("Stored %s bars for token %s", count, instrument_token)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch historical price data for one or more instruments and store it locally."
    )
    parser.add_argument(
        "--instrument",
        dest="instruments",
        action="append",
        help="Tradingsymbol or instrument name to download (repeat for multiple). Defaults to 'NIFTY 50'.",
    )
    parser.add_argument(
        "--instrument-token",
        type=int,
        dest="instrument_token",
        help="Explicit instrument token. When provided, --instrument is ignored and metadata is looked up from the instruments dump.",
    )
    parser.add_argument(
        "--segment",
        help="Optional segment filter used when resolving instruments (e.g. INDICES, NFO-OPT, NSE).",
    )
    parser.add_argument(
        "--exchange",
        help="Optional exchange filter used when resolving instruments (e.g. NSE).",
    )
    parser.add_argument(
        "--interval",
        default="day",
        help="Kite interval to request (default: day).",
    )
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=365,
        help="Number of calendar days to fetch (default: 365).",
    )
    parser.add_argument(
        "--chunk-days",
        type=int,
        help="Override the maximum number of days per request. Useful for minute-level data where Kite enforces smaller ranges.",
    )
    parser.add_argument(
        "--db-path",
        default=os.path.join("data", "market_data.db"),
        help="SQLite database path (default: data/market_data.db).",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity (default: INFO).",
    )
    return parser.parse_args()


def authenticate_kite():
    cfg = get_kite_config()
    manager = KiteTokenManager(api_key=cfg["api_key"])
    if not manager.ensure_authenticated(api_secret=cfg["api_secret"]):
        raise RuntimeError("Kite authentication failed. Run token manager to refresh access token.")
    return manager.kite


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper()), format="%(asctime)s - %(levelname)s - %(message)s")

    conn = init_db(args.db_path)
    kite = authenticate_kite()

    catalogue = kite.instruments()

    targets: List[Dict[str, Any]] = []
    if args.instrument_token is not None:
        match = next((item for item in catalogue if int(item.get("instrument_token", 0)) == args.instrument_token), None)
        if not match:
            raise ValueError(f"Instrument token {args.instrument_token} not found in instruments dump.")
        targets.append(match)
    else:
        requested = args.instruments or ["NIFTY 50"]
        for identifier in requested:
            instrument = resolve_instrument(catalogue, identifier, args.segment, args.exchange)
            targets.append(instrument)

    logger.info("Resolved %s instruments for download", len(targets))

    chunk_days = resolve_chunk_days(args.interval, args.chunk_days)

    for instrument in targets:
        try:
            fetch_and_store(
                kite,
                conn,
                instrument,
                args.interval,
                args.lookback_days,
                chunk_days,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to download %s: %s", instrument.get("tradingsymbol") or instrument.get("name"), exc)

    conn.close()


if __name__ == "__main__":
    main()


