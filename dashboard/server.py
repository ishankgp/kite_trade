"""Flask API server that serves live Iron Fly dashboard data."""

from __future__ import annotations

import os
import sys
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd
from flask import Flask, jsonify, request, send_from_directory, abort


ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from scripts import config  # noqa: E402
from scripts.generate_ironfly_dashboard import (  # noqa: E402
    find_latest_file,
    parse_event_log,
    load_state_log,
    compute_entry_prices,
    build_mtm_series,
    compute_payoff_curve,
)


app = Flask(__name__, static_folder=os.path.dirname(__file__))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def resolve_path(path: str) -> str:
    if os.path.isabs(path):
        return path
    return os.path.abspath(os.path.join(ROOT_DIR, path))


LOG_DIRECTORY = resolve_path(config.LOG_DIRECTORY)


def latest_event_log_path() -> Optional[str]:
    return find_latest_file(os.path.join(LOG_DIRECTORY, 'event_log_*.csv'))


def list_entry_events(event_log_path: str) -> List[Dict[str, object]]:
    rows = parse_event_log(event_log_path)
    entries = [row for row in rows if row.get('event_type') == 'ENTRY']
    entries.sort(key=lambda row: row.get('timestamp', ''))
    return [normalise_entry(row) for row in entries]


def normalise_entry(entry: Dict[str, object]) -> Dict[str, object]:
    details = dict(entry.get('details', {}) or {})
    strikes = details.get('strikes', {}) or {}

    if 'short_call' not in strikes and 'sell_ce' in strikes:
        strikes = {
            'short_call': strikes.get('sell_ce'),
            'short_put': strikes.get('sell_pe'),
            'long_call': strikes.get('buy_ce'),
            'long_put': strikes.get('buy_pe'),
        }

    details['strikes'] = strikes
    details.setdefault('wing_distance', config.WING_DISTANCE_DEFAULT)
    details.setdefault('lot_size', config.LOT_SIZE_FALLBACK)

    normalised = dict(entry)
    normalised['details'] = details
    return normalised


def derive_state_log_path(timestamp_iso: str) -> Optional[str]:
    try:
        timestamp = datetime.fromisoformat(timestamp_iso)
    except ValueError:
        return find_latest_file(os.path.join(LOG_DIRECTORY, 'state_log_*.csv'))

    candidate = os.path.join(LOG_DIRECTORY, f'state_log_{timestamp.date()}.csv')
    if os.path.exists(candidate):
        return candidate
    return find_latest_file(os.path.join(LOG_DIRECTORY, 'state_log_*.csv'))


def dataframe_to_records(df: pd.DataFrame) -> List[Dict[str, object]]:
    records: List[Dict[str, object]] = []
    for row in df.to_dict(orient='records'):
        processed = {}
        for key, value in row.items():
            if isinstance(value, pd.Timestamp):
                processed[key] = value.isoformat()
            elif isinstance(value, datetime):
                processed[key] = value.isoformat()
            elif pd.api.types.is_scalar(value) and pd.isna(value):
                processed[key] = None
            else:
                processed[key] = value
        records.append(processed)
    return records


def series_to_records(series: pd.Series, timestamps: pd.Series) -> List[Dict[str, object]]:
    output = []
    for value, ts in zip(series.tolist(), timestamps.tolist()):
        if isinstance(ts, pd.Timestamp):
            ts_out = ts.isoformat()
        elif isinstance(ts, datetime):
            ts_out = ts.isoformat()
        else:
            ts_out = str(ts)
        point = {
            'timestamp': ts_out,
            'mtm': None if value is None or (isinstance(value, float) and pd.isna(value)) else float(value),
        }
        output.append(point)
    return output


def dict_floatify(data: Dict[str, object]) -> Dict[str, Optional[float]]:
    result: Dict[str, Optional[float]] = {}
    for key, value in data.items():
        if value is None:
            result[key] = None
        else:
            try:
                result[key] = float(value)
            except (TypeError, ValueError):
                result[key] = None
    return result


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------


@app.get('/')
def index():
    return send_from_directory(os.path.dirname(__file__), 'index.html')


@app.get('/api/positions')
def api_positions():
    requested_log = request.args.get('event_log')
    event_log_path = resolve_path(requested_log) if requested_log else latest_event_log_path()

    if not event_log_path or not os.path.exists(event_log_path):
        abort(404, description='Event log not found')

    entries = list_entry_events(event_log_path)
    positions: List[Dict[str, object]] = []
    for entry in entries:
        details = entry['details']  # type: ignore[assignment]
        positions.append({
            'position_id': entry.get('position_id'),
            'timestamp': entry.get('timestamp'),
            'expiry': details.get('expiry'),
            'atm_strike': details.get('atm_strike'),
            'wing_distance': details.get('wing_distance'),
            'lot_size': details.get('lot_size'),
        })

    default_position_id = positions[-1]['position_id'] if positions else None

    return jsonify({
        'event_log_path': event_log_path,
        'positions': positions,
        'default_position_id': default_position_id,
    })


@app.get('/api/position/<position_id>')
def api_position(position_id: str):
    requested_log = request.args.get('event_log')
    event_log_path = resolve_path(requested_log) if requested_log else latest_event_log_path()

    if not event_log_path or not os.path.exists(event_log_path):
        abort(404, description='Event log not found')

    entries = list_entry_events(event_log_path)
    entry = next((item for item in entries if item.get('position_id') == position_id), None)
    if not entry:
        abort(404, description=f'Position {position_id} not found in event log')

    timestamp_iso = entry.get('timestamp')
    requested_state_log = request.args.get('state_log')
    state_log_path = resolve_path(requested_state_log) if requested_state_log else derive_state_log_path(timestamp_iso)

    if not state_log_path or not os.path.exists(state_log_path):
        abort(404, description='State log not found')

    try:
        state_df = load_state_log(state_log_path, position_id)
    except ValueError as exc:  # No rows for this position
        abort(404, description=str(exc))

    entry_prices = compute_entry_prices(state_df)
    lot_size = entry['details'].get('lot_size', config.LOT_SIZE_FALLBACK)  # type: ignore[index]
    mtm_series = build_mtm_series(state_df, entry_prices, lot_size)
    payoff_df = compute_payoff_curve(entry['details'], entry_prices)  # type: ignore[arg-type]

    state_records = dataframe_to_records(state_df)
    mtm_records = series_to_records(mtm_series, state_df['timestamp'])
    payoff_records = [
        {
            'underlying': int(row['underlying']),
            'payoff': float(row['payoff']),
        }
        for row in payoff_df.to_dict(orient='records')
    ]

    last_updated = state_records[-1]['timestamp'] if state_records else timestamp_iso

    return jsonify({
        'event_log_path': event_log_path,
        'state_log_path': state_log_path,
        'position': {
            'position_id': entry.get('position_id'),
            'timestamp': timestamp_iso,
            'details': entry['details'],  # type: ignore[index]
        },
        'entry_prices': dict_floatify(entry_prices),
        'state': state_records,
        'mtm_series': mtm_records,
        'payoff': payoff_records,
        'last_updated': last_updated,
    })


@app.get('/api/health')
def api_health():
    return jsonify({'status': 'ok'})


if __name__ == '__main__':
    port = int(os.environ.get('DASHBOARD_PORT', '5050'))
    app.run(host='0.0.0.0', port=port, debug=False)


