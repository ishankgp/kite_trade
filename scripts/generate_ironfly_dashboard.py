# Ensure we can import from project root
import os
import sys
import json
import glob
import argparse
from datetime import datetime
from typing import Dict, Any, Optional

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import scripts.config as config


def find_latest_file(pattern: str) -> Optional[str]:
    files = sorted(glob.glob(pattern))
    return files[-1] if files else None


def parse_event_log(event_log_path: str) -> list:
    entries = []
    with open(event_log_path, 'r', encoding='utf-8') as f:
        header = f.readline()
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split(',', 3)
            if len(parts) < 4:
                continue
            timestamp, position_id, event_type, rest = parts

            if not rest.startswith('"'):
                continue

            end_idx = rest.rfind('",0')
            if end_idx == -1:
                continue
            details_raw = rest[1:end_idx]
            tail = rest[end_idx+3:]  # skip ",0
            if tail.startswith(','):
                tail = tail[1:]
            order_ids = [oid for oid in tail.split(',') if oid]

            try:
                details_json = json.loads(details_raw)
            except json.JSONDecodeError:
                continue

            entries.append({
                'timestamp': timestamp,
                'position_id': position_id,
                'event_type': event_type,
                'details': details_json,
                'pnl_realized': 0,
                'order_ids': order_ids
            })
    return entries


def load_latest_entry(event_log_path: str, position_id: Optional[str] = None) -> Dict[str, Any]:
    entries = parse_event_log(event_log_path)
    if not entries:
        raise ValueError("No entries found in event log")

    if position_id:
        entries = [row for row in entries if row['position_id'] == position_id and row['event_type'] == 'ENTRY']
        if not entries:
            raise ValueError(f"Position ID {position_id} not found in event log")
    else:
        entries = [row for row in entries if row['event_type'] == 'ENTRY']
        if not entries:
            raise ValueError("No ENTRY events found in event log")

    row = entries[-1]
    details = row['details']
    details['timestamp'] = row['timestamp']
    details['position_id'] = row['position_id']
    details['event_log_path'] = event_log_path
    return details


def load_state_log(state_log_path: str, position_id: str) -> pd.DataFrame:
    df = pd.read_csv(state_log_path)
    if 'position_id' not in df.columns:
        raise ValueError(f"State log at {state_log_path} missing position_id column")
    df = df[df['position_id'] == position_id].copy()
    if df.empty:
        raise ValueError(f"No state log rows for position {position_id}")
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    # Ensure numeric columns
    float_cols = [
        'banknifty_spot',
        'short_call_ltp', 'short_put_ltp',
        'long_call_ltp', 'long_put_ltp'
    ]
    for col in float_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    return df


def compute_entry_prices(state_df: pd.DataFrame) -> Dict[str, float]:
    first_row = state_df.iloc[0]
    return {
        'short_call': first_row['short_call_ltp'],
        'short_put': first_row['short_put_ltp'],
        'long_call': first_row['long_call_ltp'],
        'long_put': first_row['long_put_ltp']
    }


def extract_strike(value: Any) -> int:
    if isinstance(value, (int, float)):
        return int(value)
    digits = ''.join(ch for ch in str(value) if ch.isdigit())
    if not digits:
        raise ValueError(f"Unable to parse strike from {value}")
    return int(digits)


def compute_mtm(series: pd.Series, entry_price: float, lot_size: int, side: str) -> pd.Series:
    if side == 'short':
        return (entry_price - series) * lot_size
    return (series - entry_price) * lot_size


def build_mtm_series(state_df: pd.DataFrame, entry_prices: Dict[str, float], lot_size: int) -> pd.Series:
    pnl_sc = compute_mtm(state_df['short_call_ltp'], entry_prices['short_call'], lot_size, 'short')
    pnl_sp = compute_mtm(state_df['short_put_ltp'], entry_prices['short_put'], lot_size, 'short')
    pnl_lc = compute_mtm(state_df['long_call_ltp'], entry_prices['long_call'], lot_size, 'long')
    pnl_lp = compute_mtm(state_df['long_put_ltp'], entry_prices['long_put'], lot_size, 'long')
    return pnl_sc + pnl_sp + pnl_lc + pnl_lp


def compute_payoff_curve(details: Dict[str, Any], entry_prices: Dict[str, float]) -> pd.DataFrame:
    strikes = details['strikes']
    wing = details.get('wing_distance', config.WING_DISTANCE_DEFAULT)
    lot_size = details.get('lot_size', config.LOT_SIZE_FALLBACK)

    sc_strike = extract_strike(strikes['short_call'])
    sp_strike = extract_strike(strikes['short_put'])
    lc_strike = extract_strike(strikes['long_call'])
    lp_strike = extract_strike(strikes['long_put'])

    price_min = min(lp_strike, sp_strike) - wing
    price_max = max(lc_strike, sc_strike) + wing
    price_points = list(range(price_min, price_max + 100, 100))
    data = []
    for price in price_points:
        pnl_sc = (entry_prices['short_call'] - max(0, price - sc_strike)) * lot_size
        pnl_sp = (entry_prices['short_put'] - max(0, sp_strike - price)) * lot_size
        pnl_lc = (max(0, price - lc_strike) - entry_prices['long_call']) * lot_size
        pnl_lp = (max(0, lp_strike - price) - entry_prices['long_put']) * lot_size
        total = pnl_sc + pnl_sp + pnl_lc + pnl_lp
        data.append({'underlying': price, 'payoff': total})
    return pd.DataFrame(data)


def build_dashboard(state_df: pd.DataFrame, mtm_series: pd.Series, payoff_df: pd.DataFrame,
                    details: Dict[str, Any], output_path: str) -> None:
    fig = make_subplots(rows=2, cols=1, shared_xaxes=False, vertical_spacing=0.12,
                        subplot_titles=("Mark-to-Market Timeline", "Expiry Payoff Curve"))

    fig.add_trace(
        go.Scatter(x=state_df['timestamp'], y=mtm_series, mode='lines+markers',
                   name='MTM P&L (₹)'),
        row=1, col=1
    )

    fig.add_trace(
        go.Scatter(x=payoff_df['underlying'], y=payoff_df['payoff'], mode='lines',
                   name='Payoff @ Expiry'),
        row=2, col=1
    )

    fig.update_xaxes(title_text="Time", row=1, col=1)
    fig.update_yaxes(title_text="P&L (₹)", row=1, col=1)
    fig.update_xaxes(title_text="Underlying Price", row=2, col=1)
    fig.update_yaxes(title_text="Payoff (₹)", row=2, col=1)

    metadata_text = [
        f"Position: {details['position_id']}",
        f"Entry Timestamp: {details['timestamp']}",
        f"ATM Strike: {details.get('atm_strike')}",
        f"Wing Distance: {details.get('wing_distance')} pts",
        f"Expiry: {details.get('expiry')}",
        f"Lot Size: {details.get('lot_size')}"
    ]

    fig.add_annotation(
        text="<br>".join(metadata_text),
        align='left',
        showarrow=False,
        xref='paper', yref='paper',
        x=0, y=1.18
    )

    fig.update_layout(
        title="Phoenix Iron Fly Simulation Dashboard",
        height=800,
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1)
    )

    fig.write_html(output_path, include_plotlyjs='cdn', full_html=True)


def main():
    parser = argparse.ArgumentParser(description="Generate Iron Fly dashboard HTML")
    parser.add_argument('--position-id', help='Specific position ID to visualise')
    parser.add_argument('--event-log', help='Path to event log CSV')
    parser.add_argument('--state-log', help='Path to state log CSV')
    parser.add_argument('--output', help='Output HTML path')
    args = parser.parse_args()

    log_dir = config.LOG_DIRECTORY
    ensure_dir = os.path.join(log_dir, 'plots')
    os.makedirs(ensure_dir, exist_ok=True)

    event_log_path = args.event_log or find_latest_file(os.path.join(log_dir, 'event_log_*.csv'))
    if not event_log_path:
        raise FileNotFoundError("No event log files found")

    details = load_latest_entry(event_log_path, args.position_id)

    # Determine state log date from event timestamp
    timestamp = datetime.fromisoformat(details['timestamp'])
    state_log_path = args.state_log or os.path.join(log_dir, f"state_log_{timestamp.date()}.csv")
    if not os.path.exists(state_log_path):
        # Fallback to latest state log
        fallback = find_latest_file(os.path.join(log_dir, 'state_log_*.csv'))
        if not fallback:
            raise FileNotFoundError("No state log files found")
        state_log_path = fallback

    state_df = load_state_log(state_log_path, details['position_id'])
    entry_prices = compute_entry_prices(state_df)
    mtm_series = build_mtm_series(state_df, entry_prices, details.get('lot_size', config.LOT_SIZE_FALLBACK))
    payoff_df = compute_payoff_curve(details, entry_prices)

    output_path = args.output or os.path.join(ensure_dir, f"{details['position_id']}.html")
    build_dashboard(state_df, mtm_series, payoff_df, details, output_path)
    print(f"Dashboard written to {output_path}")


if __name__ == '__main__':
    main()
