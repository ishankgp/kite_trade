import os
import sys
import json
import logging
from datetime import datetime, timedelta, time as dt_time
from zoneinfo import ZoneInfo
from typing import Dict, Any, Optional
import pandas as pd
import time
import math

# Adjust path to import from the root directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from kiteconnect import KiteConnect
from kite_token_manager import KiteTokenManager
import scripts.config as config

# --- LOGGING SETUP ---
def setup_logging():
    ensure_directory(config.LOG_DIRECTORY)
    
    # Get current date for log file names
    today_str = datetime.now().strftime("%Y-%m-%d")
    month_str = datetime.now().strftime("%Y-%m")

    # Event Log (Captain's Log)
    event_log_file = os.path.join(config.LOG_DIRECTORY, f"event_log_{month_str}.csv")
    event_logger = logging.getLogger('event_logger')
    event_logger.setLevel(logging.INFO)
    # Clear existing handlers to avoid duplicate logs
    if event_logger.hasHandlers():
        event_logger.handlers.clear()
    event_handler = logging.FileHandler(event_log_file)
    event_logger.addHandler(event_handler)

    # State Log (Ticker Tape)
    state_log_file = os.path.join(config.LOG_DIRECTORY, f"state_log_{today_str}.csv")
    state_logger = logging.getLogger('state_logger')
    state_logger.setLevel(logging.INFO)
    if state_logger.hasHandlers():
        state_logger.handlers.clear()
    state_handler = logging.FileHandler(state_log_file)
    state_logger.addHandler(state_handler)

    # Create headers if files are new or empty
    if not os.path.exists(event_log_file) or os.path.getsize(event_log_file) == 0:
         with open(event_log_file, 'w') as f:
            f.write("timestamp,position_id,event_type,details,pnl_realized,kite_order_ids\n")

    if not os.path.exists(state_log_file) or os.path.getsize(state_log_file) == 0:
        with open(state_log_file, 'w') as f:
            f.write("timestamp,position_id,banknifty_spot,unrealized_pnl,position_delta,"
                    "short_call_symbol,short_call_ltp,short_call_delta,"
                    "short_put_symbol,short_put_ltp,short_put_delta,"
                    "long_call_symbol,long_call_ltp,"
                    "long_put_symbol,long_put_ltp\n")

    return event_logger, state_logger

# --- Utility helpers ---
def ensure_directory(path: str) -> None:
    if not os.path.exists(path):
        os.makedirs(path)


def round_to_nearest_strike(value: float, strikes: pd.Series) -> int:
    if strikes.empty:
        return int(round(value / 100) * 100)
    return int(strikes.iloc[(strikes - value).abs().argsort()].iloc[0])


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


class IronFlyTrader:
    def __init__(self, kite: KiteConnect, event_logger, state_logger):
        self.kite = kite
        self.event_logger = event_logger
        self.state_logger = state_logger
        self.instruments_df: Optional[pd.DataFrame] = None
        self.banknifty_instrument_token: Optional[int] = None
        self.banknifty_symbol_token: Optional[int] = None
        self.lot_size: int = config.LOT_SIZE_FALLBACK
        self.option_chain_cache: Dict[str, pd.DataFrame] = {}
        self.position_id: Optional[str] = None
        self.current_plan: Optional[Dict[str, Any]] = None
        self.last_state_log_time: Optional[datetime] = None
        self.last_llm_confidence: Optional[float] = None
        self.load_instruments()

    # ------------------------------------------------------------------
    # Pre-trade guardrails
    # ------------------------------------------------------------------
    def is_trading_window_open(self) -> bool:
        tz = ZoneInfo(config.MARKET_TIMEZONE)
        now = datetime.now(tz)

        if config.ALLOW_AFTER_HOURS_SIMULATION:
            return True

        market_open = datetime.combine(now.date(), dt_time.fromisoformat(config.MARKET_OPEN_TIME), tz)
        market_close = datetime.combine(now.date(), dt_time.fromisoformat(config.MARKET_CLOSE_TIME), tz)

        if now < market_open:
            logging.info("Pre-trade guard: market not open yet.")
            return False

        cutoff = market_close - timedelta(minutes=config.BLOCK_NEW_ENTRIES_LAST_MINUTES)
        if now > cutoff:
            logging.info("Pre-trade guard: inside last-entry blackout window.")
            return False

        return True

    def check_margin_buffer(self) -> bool:
        try:
            response = self.kite.margins(segment='equity')  # includes derivatives funds
            available = response.get('net', 0)
            required = config.REQUIRED_MARGIN_PER_SET * config.MAX_SETS * config.MARGIN_BUFFER_MULTIPLIER
            if available < required:
                logging.info(f"Pre-trade guard: Insufficient margin. required={required}, available={available}")
                return False
            return True
        except Exception as e:
            logging.warning(f"Margin check failed ({e}); blocking entry for safety.")
            return False

    def in_event_blackout(self) -> bool:
        if not config.EVENT_BLACKOUTS:
            return False
        now = datetime.utcnow()
        for window in config.EVENT_BLACKOUTS:
            try:
                start = datetime.fromisoformat(window['start']).replace(tzinfo=None)
                end = datetime.fromisoformat(window['end']).replace(tzinfo=None)
                if start <= now <= end:
                    logging.info(f"Pre-trade guard: event blackout active ({window}).")
                    return True
            except Exception:
                logging.warning(f"Invalid blackout window format: {window}")
        return False

    # ------------------------------------------------------------------
    # LLM gating -------------------------------------------------------
    # ------------------------------------------------------------------
    def should_enter_via_llm(self, features: Dict[str, Any]) -> bool:
        if not config.LLM_ENABLED:
            self.last_llm_confidence = None
            return True

        try:
            from openai import OpenAI  # type: ignore
        except ImportError:
            logging.warning("LLM gating enabled but openai package not installed; blocking entry.")
            return False

        api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            logging.warning("OPENAI_API_KEY not set; blocking entry as per safety policy.")
            return False

        client = OpenAI(api_key=api_key)
        system_prompt = (
            "You are an expert Indian index options trader. Analyze BankNifty monthly option chain stats, "
            "technicals, and near-term macro/news. Recommend whether to enter a risk-defined Iron Fly now. "
            "Consider liquidity (spreads, depth) and avoid entries near major policy headlines. Output JSON with keys: enter (bool), confidence (0-1), reason (string)."
        )

        try:
            response = client.responses.create(
                model=config.LLM_MODEL,
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(features)}
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
                timeout=config.LLM_TIMEOUT_SECONDS
            )
            content = response.output[0].content[0].text  # type: ignore
            payload = json.loads(content)
            self.last_llm_confidence = payload.get('confidence')
            should_enter = payload.get('enter', False)
            if should_enter and self.last_llm_confidence is not None and self.last_llm_confidence < config.LLM_CONFIDENCE_THRESHOLD:
                logging.info(f"LLM gate confidence {self.last_llm_confidence:.2f} below threshold {config.LLM_CONFIDENCE_THRESHOLD}.")
                return False
            logging.info(f"LLM gate decision enter={should_enter}, confidence={self.last_llm_confidence}, reason={payload.get('reason')}")
            return bool(should_enter)
        except Exception as e:
            logging.warning(f"LLM gating failed: {e}")
            return False if not config.LLM_NOOP_ON_ERROR else True
    def load_instruments(self):
        """Loads instruments and finds BANKNIFTY tokens and lot size."""
        try:
            instruments_list = self.kite.instruments()
            self.instruments_df = pd.DataFrame(instruments_list)

            nifty_bank_series = self.instruments_df[
                (self.instruments_df['name'] == 'NIFTY BANK') &
                (self.instruments_df['segment'] == 'INDICES')
            ]
            if nifty_bank_series.empty:
                logging.error("Could not find 'NIFTY BANK' in the INDICES segment.")
                sys.exit(1)

            self.banknifty_instrument_token = int(nifty_bank_series.iloc[0]['instrument_token'])

            # Determine lot size from BANKNIFTY options
            options_series = self.instruments_df[
                (self.instruments_df['name'] == 'BANKNIFTY') &
                (self.instruments_df['segment'] == config.EXCHANGE)
            ]
            if options_series.empty:
                logging.error("BANKNIFTY options not found in instruments dump.")
                sys.exit(1)

            lot_sizes = options_series['lot_size'].dropna().unique()
            if lot_sizes.size > 0:
                self.lot_size = int(lot_sizes[0])
            else:
                logging.warning("Lot size not found in instruments dump, using fallback value.")

            logging.info("Successfully loaded instruments and lot size.")
            logging.info(f"BANKNIFTY instrument token: {self.banknifty_instrument_token}, lot size: {self.lot_size}")

        except Exception as e:
            logging.error(f"Error loading instruments or determining lot size: {e}")
            sys.exit(1)
    
    def get_atm_strike(self) -> Optional[int]:
        """Fetches the current spot price and determines the nearest strike price."""
        spot_price = self.get_spot_price()
        if spot_price is None:
            return None
        try:
            strikes = self.instruments_df[
                (self.instruments_df['name'] == 'BANKNIFTY') &
                (self.instruments_df['segment'] == config.EXCHANGE)
            ]['strike'].dropna().drop_duplicates().sort_values()
            atm_strike = round_to_nearest_strike(spot_price, strikes)
            logging.info(f"Bank Nifty Spot: {spot_price}, ATM Strike: {atm_strike}")
            return atm_strike
        except Exception as e:
            logging.error(f"Error getting spot price or calculating ATM strike: {e}")
            return None

    def get_spot_price(self) -> Optional[float]:
        try:
            instrument_to_fetch = str(self.banknifty_instrument_token)
            ltp_data = self.kite.ltp(instrument_to_fetch)
            if not ltp_data or instrument_to_fetch not in ltp_data:
                logging.error(f"Could not get LTP for instrument token: {instrument_to_fetch}")
                return None
            return ltp_data[instrument_to_fetch]['last_price']
        except Exception as e:
            logging.error(f"Error fetching spot price: {e}")
            return None
            
    def compute_wing_distance(self, spot_price: float) -> int:
        """Computes wing distance using ATR if enabled."""
        if not config.USE_SIGMA_WINGS:
            return config.WING_DISTANCE_DEFAULT

        try:
            # Fetch recent candles to compute ATR14 using daily data
            # Candle API: interval="day", last 30 sessions
            from_date = (datetime.now() - timedelta(days=60))
            to_date = datetime.now()
            candles = self.kite.historical_data(
                self.banknifty_instrument_token,
                from_date.strftime('%Y-%m-%d %H:%M:%S'),
                to_date.strftime('%Y-%m-%d %H:%M:%S'),
                interval="day",
            )
            if not candles or len(candles) < 15:
                logging.warning("Insufficient candles for ATR, using default wing distance.")
                return config.WING_DISTANCE_DEFAULT

            df = pd.DataFrame(candles)
            df['high_low'] = df['high'] - df['low']
            df['high_prev_close'] = (df['high'] - df['close'].shift(1)).abs()
            df['low_prev_close'] = (df['low'] - df['close'].shift(1)).abs()
            df['true_range'] = df[['high_low', 'high_prev_close', 'low_prev_close']].max(axis=1)
            atr = df['true_range'].rolling(window=14).mean().iloc[-1]
            if pd.isna(atr):
                logging.warning("ATR calculation failed, using default wing distance.")
                return config.WING_DISTANCE_DEFAULT

            sigma_distance = atr * config.SIGMA_MULTIPLIER
            wing_distance = int(round(clamp(sigma_distance, config.MIN_WING_DISTANCE, config.MAX_WING_DISTANCE) / 100) * 100)
            logging.info(f"ATR-based wing distance: {wing_distance} (ATR={atr:.2f})")
            return wing_distance

        except Exception as e:
            logging.warning(f"ATR-based wing distance failed: {e}. Using default.")
            return config.WING_DISTANCE_DEFAULT

    def find_iron_fly_contracts(self, atm_strike: int, wing_distance: int) -> Optional[Dict[str, Any]]:
        """Finds the CE and PE contracts for the Iron Fly."""
        
        bn_options = self.instruments_df[
            (self.instruments_df['name'] == 'BANKNIFTY') &
            (self.instruments_df['segment'] == config.EXCHANGE)
        ]

        bn_options = bn_options.copy()
        bn_options['expiry'] = pd.to_datetime(bn_options['expiry'])
        
        # --- MODIFIED EXPIRY LOGIC ---
        # Only consider options that expire today or in the future
        today = pd.to_datetime(datetime.now().date())
        future_options = bn_options[bn_options['expiry'] >= today].copy()

        # Find the soonest monthly expiry
        # We identify monthly expiries by grouping by month and taking the last expiry date
        future_options['expiry_month'] = future_options['expiry'].dt.to_period('M')
        monthly_expiries = future_options.groupby('expiry_month')['expiry'].max().sort_values()

        if monthly_expiries.empty:
            logging.error("No future monthly expiries found.")
            return None
            
        target_expiry = monthly_expiries.iloc[0]

        # --- FINAL EXPIRY CHECK ---
        # If the chosen expiry is today, check if we are past market close time.
        if target_expiry.date() == datetime.now().date():
            market_close = datetime.now().replace(hour=15, minute=30, second=0, microsecond=0)
            if datetime.now() > market_close:
                logging.warning(f"Target expiry {target_expiry.date()} is today, but market is closed. Selecting next month.")
                if len(monthly_expiries) > 1:
                    target_expiry = monthly_expiries.iloc[1]
                else:
                    logging.error("No further monthly expiry available to trade.")
                    return None
        # --- END FINAL EXPIRY CHECK ---

        logging.info(f"Targeting next available monthly expiry: {target_expiry.strftime('%Y-%m-%d')}")

        options_at_expiry = bn_options[bn_options['expiry'] == target_expiry]

        try:
            short_call = options_at_expiry[(options_at_expiry['strike'] == atm_strike) & (options_at_expiry['instrument_type'] == 'CE')].iloc[0]
            short_put = options_at_expiry[(options_at_expiry['strike'] == atm_strike) & (options_at_expiry['instrument_type'] == 'PE')].iloc[0]
            
            long_call_strike = atm_strike + wing_distance
            long_put_strike = atm_strike - wing_distance

            long_call = options_at_expiry[(options_at_expiry['strike'] == long_call_strike) & (options_at_expiry['instrument_type'] == 'CE')].iloc[0]
            long_put = options_at_expiry[(options_at_expiry['strike'] == long_put_strike) & (options_at_expiry['instrument_type'] == 'PE')].iloc[0]

            plan = {
                'legs': {
                    'short_call': short_call['tradingsymbol'],
                    'short_put': short_put['tradingsymbol'],
                    'long_call': long_call['tradingsymbol'],
                    'long_put': long_put['tradingsymbol']
                },
                'atm_strike': atm_strike,
                'wing_distance': wing_distance,
                'expiry': target_expiry,
                'lot_size': self.lot_size
            }
            logging.info(f"Found Iron Fly contracts: {plan['legs']}")
            self.current_plan = plan
            return plan

        except IndexError:
            logging.error(f"Could not find one or more option contracts for ATM strike {atm_strike} and expiry {target_expiry.strftime('%Y-%m-%d')}.")
            return None

    def place_iron_fly_orders(self, plan: Dict[str, Any]) -> Optional[list]:
        """Simulates placing the 4 orders for the Iron Fly."""
        legs = plan['legs']
        orders = [
            {"tradingsymbol": legs['short_call'], "transaction_type": "SELL"},
            {"tradingsymbol": legs['short_put'], "transaction_type": "SELL"},
            {"tradingsymbol": legs['long_call'], "transaction_type": "BUY"},
            {"tradingsymbol": legs['long_put'], "transaction_type": "BUY"}
        ]

        order_ids = []
        logging.info("--- SIMULATING ORDER PLACEMENT ---")
        for order_spec in orders:
            try:
                # --- THIS IS THE SIMULATION ---
                # We are not calling self.kite.place_order()
                # Instead, we log the intended action and create a fake order ID.
                fake_order_id = f"SIM_{int(time.time() * 1000)}"
                order_ids.append(fake_order_id)
                logging.info(f"[SIMULATED] Placing {order_spec['transaction_type']} order for {order_spec['tradingsymbol']} quantity={self.lot_size * config.MAX_SETS}")
                logging.info(f"[SIMULATED] Order ID: {fake_order_id}")
                time.sleep(0.1) # Simulate network latency
                # --- END SIMULATION ---
                
            except Exception as e:
                # This block should not be hit in simulation, but is good practice
                logging.error(f"An unexpected error occurred during simulation for {order_spec['tradingsymbol']}: {e}")
                return None
        
        logging.info("--- SIMULATION COMPLETE ---")
        self.log_entry_event(plan, order_ids)
        return order_ids

    def log_entry_event(self, plan: Dict[str, Any], order_ids: list) -> None:
        legs = plan['legs']
        details = {
          "reason": "LLM Signal Favorable" if config.LLM_ENABLED else "Simulated Entry",
          "atm_strike": plan['atm_strike'],
          "wing_distance": plan['wing_distance'],
          "lot_size": plan['lot_size'],
          "expiry": plan['expiry'].strftime('%Y-%m-%d'),
          "llm_confidence": getattr(self, 'last_llm_confidence', None),
          "strikes": plan['legs'],
          "initial_credit": "N/A",
          "max_profit": "N/A"
        }

        position_id = f"BNF_IFLY_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        log_entry = (
            f"{datetime.now().isoformat()},"
            f"{position_id},"
            f"ENTRY,"
            f'"{json.dumps(details)}",'
            f"0,"
            f"{','.join(map(str, order_ids))}"
        )
        self.event_logger.info(log_entry)
        logging.info(f"Logged ENTRY event for position {position_id}")
        self.position_id = position_id
        self.last_state_log_time = None

    def log_state_snapshot(self, spot_price: float) -> None:
        if not self.current_plan or not self.position_id:
            return
        try:
            legs = self.current_plan['legs']
            quote_keys = [f"{config.OPTION_EXCHANGE}:{symbol}" for symbol in legs.values()]
            quotes = self.kite.quote(quote_keys)
            snapshot = {
                "timestamp": datetime.now().isoformat(),
                "position_id": self.position_id,
                "banknifty_spot": spot_price,
                "unrealized_pnl": "N/A",
                "position_delta": "N/A",
                "short_call_symbol": legs['short_call'],
                "short_call_ltp": quotes.get(f"{config.OPTION_EXCHANGE}:{legs['short_call']}", {}).get('last_price'),
                "short_call_delta": "N/A",
                "short_put_symbol": legs['short_put'],
                "short_put_ltp": quotes.get(f"{config.OPTION_EXCHANGE}:{legs['short_put']}", {}).get('last_price'),
                "short_put_delta": "N/A",
                "long_call_symbol": legs['long_call'],
                "long_call_ltp": quotes.get(f"{config.OPTION_EXCHANGE}:{legs['long_call']}", {}).get('last_price'),
                "long_put_symbol": legs['long_put'],
                "long_put_ltp": quotes.get(f"{config.OPTION_EXCHANGE}:{legs['long_put']}", {}).get('last_price')
            }
            self.state_logger.info(",".join(str(snapshot[col]) for col in ['timestamp','position_id','banknifty_spot','unrealized_pnl','position_delta','short_call_symbol','short_call_ltp','short_call_delta','short_put_symbol','short_put_ltp','short_put_delta','long_call_symbol','long_call_ltp','long_put_symbol','long_put_ltp']))
        except Exception as e:
            logging.warning(f"Failed to log state snapshot: {e}")

    def evaluate_and_execute_entry(self, plan: Dict[str, Any]) -> bool:
        if not self.is_trading_window_open():
            return False
        if self.in_event_blackout():
            return False
        if not self.check_margin_buffer():
            return False

        spot = self.get_spot_price()
        if spot is None:
            return False

        features = {
            "spot": spot,
            "atm_strike": plan['atm_strike'],
            "wing_distance": plan['wing_distance'],
            "expiry": plan['expiry'].strftime('%Y-%m-%d'),
            "lot_size": plan['lot_size'],
            "legs": plan['legs']
        }

        if not self.should_enter_via_llm(features):
            logging.info("LLM gate or fallback declined entry.")
            return False

        order_ids = self.place_iron_fly_orders(plan)
        if not order_ids:
            return False

        self.log_state_snapshot(spot)
        return True


def main():
    event_logger, state_logger = setup_logging()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    logging.info("--- Starting Phoenix: The Intelligent Iron Fly Trader ---")

    try:
        from env_loader import get_kite_config
        _cfg = get_kite_config()
        API_KEY = _cfg['api_key']
        API_SECRET = _cfg['api_secret']

        manager = KiteTokenManager(api_key=API_KEY)
        if not manager.ensure_authenticated(api_secret=API_SECRET):
             raise Exception("Kite authentication failed.")
        
        kite = manager.kite
        logging.info("Kite authentication successful.")

    except Exception as e:
        logging.error(f"Authentication Error: {e}")
        sys.exit(1)
    
    trader = IronFlyTrader(kite, event_logger, state_logger)
    
    logging.info("Trader initialized. Ready for market analysis.")

    atm_strike = trader.get_atm_strike()

    if atm_strike:
        wing_distance = trader.compute_wing_distance(atm_strike)
        plan = trader.find_iron_fly_contracts(atm_strike, wing_distance)
        if plan:
            logging.info("Proceeding to evaluate entry conditions.")
            trader.evaluate_and_execute_entry(plan)
    

if __name__ == "__main__":
    main()
