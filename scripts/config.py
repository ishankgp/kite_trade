# --- LOGGING CONFIGURATION ---
LOG_DIRECTORY = "./trade_logs/"

# --- TRADING CONFIGURATION ---
# Note: Specific instrument names are required for API calls.
INSTRUMENT = "NFO:BANKNIFTY"  # Used for context, not for quotes
INDEX_INSTRUMENT = "INDICES:NIFTY BANK"  # Used to get the spot price
EXCHANGE = "NFO-OPT"  # The specific segment for Bank Nifty options
OPTION_EXCHANGE = "NFO"  # Prefix used for quote requests
PRODUCT = "MIS"
# Default lot size fallback if instruments dump unavailable
LOT_SIZE_FALLBACK = 15

# --- WING SELECTION PARAMETERS ---
USE_SIGMA_WINGS = True
SIGMA_MULTIPLIER = 0.8
MIN_WING_DISTANCE = 700
MAX_WING_DISTANCE = 1200
WING_DISTANCE_DEFAULT = 500

# --- RISK & MARGINS ---
REQUIRED_MARGIN_PER_SET = 250000  # INR, conservative placeholder for 1 Iron Fly set
MARGIN_BUFFER_MULTIPLIER = 1.2
MAX_SETS = 1
PER_ORDER_SLIPPAGE_RUPEES = 1.0

# --- PRE-TRADE GUARDS ---
MARKET_TIMEZONE = "Asia/Kolkata"
MARKET_OPEN_TIME = "09:25"
MARKET_CLOSE_TIME = "15:00"
BLOCK_NEW_ENTRIES_LAST_MINUTES = 30
ALLOW_AFTER_HOURS_SIMULATION = True
EVENT_BLACKOUTS = []  # list of {"start": iso, "end": iso}

# --- LLM GATE (OPTIONAL) ---
LLM_ENABLED = False
LLM_MODEL = "gpt-5"
LLM_CONFIDENCE_THRESHOLD = 0.62
LLM_TIMEOUT_SECONDS = 120
LLM_NOOP_ON_ERROR = True


# --- STRATEGY PARAMETERS ---
PROFIT_TARGET_PERCENT = 0.40  # Placeholder - to be calculated via MTM engine
STOP_LOSS_PERCENT = 0.20
DELTA_BREACH_THRESHOLD = 0.35
