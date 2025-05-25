# backend/config.py

import os
from typing import List, Dict

# === CORE PLATFORM SETTINGS ===
PLATFORM_NAME = "Atticus"
VERSION = "2.1"
DEMO_MODE = True

# === CONTRACT SPECIFICATIONS ===
# *** Updated contract size to 0.1 BTC for institutional standard ***
STANDARD_CONTRACT_SIZE_BTC = 0.1  # Each contract represents 0.1 BTC
CONTRACT_SIZES_AVAILABLE = [0.1]  # Institutional contract size

# === EXPIRY CONFIGURATIONS ===
# *** UPDATED: Removed 5-minute "gambling" expiry for professional credibility ***
AVAILABLE_EXPIRIES_MINUTES = [
    15,  # 15 minutes - shortest professional timeframe
    60,  # 1 hour
    240, # 4 hours
    480  # 8 hours
]

# *** UPDATED: Removed "Turbo" label, keeping professional naming ***
EXPIRY_LABELS = {
    15: "Express", 
    60: "Hourly",
    240: "4-Hour",
    480: "8-Hour"
}

# === PRICING ENGINE SETTINGS ===
RISK_FREE_RATE = 0.05  # 5% annual risk-free rate
MIN_VOLATILITY = 0.50  # 50% minimum annualized volatility floor
MAX_VOLATILITY = 2.50  # 250% maximum volatility cap
DEFAULT_VOLATILITY = 0.80  # 80% default if calculation fails
DEFAULT_VOLATILITY_FOR_BASIC_BS = 0.80

# Advanced volatility settings
VOLATILITY_REGIME_DETECTION = True
VOLATILITY_EWMA_ALPHA = 0.1
VOLATILITY_GARCH_ENABLED = False
ML_VOL_TRAINING_INTERVAL = 500
PRICE_CHANGE_THRESHOLD_FOR_BROADCAST = 0.0001

# === STRIKE GENERATION ===
# *** UPDATED: Removed 5-minute strike config, optimized for professional expiries ***
STRIKE_RANGES_BY_EXPIRY = {
    15: {"num_itm": 7, "num_otm": 7, "step_pct": 0.005},   # Express - tight spacing
    60: {"num_itm": 10, "num_otm": 10, "step_pct": 0.01},  # Hourly - moderate spacing
    240: {"num_itm": 12, "num_otm": 12, "step_pct": 0.02}, # 4-Hour - wider spacing
    480: {"num_itm": 15, "num_otm": 15, "step_pct": 0.03}  # 8-Hour - widest spacing
}

STRIKE_ROUNDING_NEAREST = 10  # Round strikes to nearest $10

# === DATA FEED SETTINGS ===
EXCHANGES_ENABLED = ["coinbase", "kraken", "okx"]
PRIMARY_EXCHANGE = "coinbase"
DATA_BROADCAST_INTERVAL_SECONDS = 1.0
PRICE_HISTORY_MAX_POINTS = 10000

# === ALPHA SIGNAL SETTINGS ===
ALPHA_SIGNALS_ENABLED = False
BAR_PORTION_LOOKBACK = 20
REGIME_DETECTION_LOOKBACK = 100
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
REGIME_TRAINING_INTERVAL = 1000

# === FEATURE FLAGS ===
SENTIMENT_ANALYSIS_ENABLED = False
USE_RL_HEDGER = False
USE_ML_VOLATILITY = False
REGIME_DETECTION_ENABLED = True

# === HEDGING SIMULATION ===
HEDGING_ENABLED = True
DELTA_HEDGE_FREQUENCY_MINUTES = 5
HEDGE_SLIPPAGE_BPS = 2

# === RISK MANAGEMENT ===
MAX_SINGLE_USER_EXPOSURE_BTC = 10.0
MAX_PLATFORM_NET_DELTA_BTC = 100.0
MARGIN_REQUIREMENT_MULTIPLIER = 1.5

# === API SETTINGS ===
API_PORT = 8000
API_HOST = "localhost"

CORS_ORIGINS = [
    "*",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://preview--atticus-option-flow.lovable.app"
]

API_STARTUP_TIMEOUT = 20
WEBSOCKET_TIMEOUT_SECONDS = 30

# === LOGGING ===
LOG_LEVEL = "INFO"
LOG_FILE = "logs/atticus.log"

# === DATABASE ===
DATABASE_URL = "sqlite:///./atticus_demo.db"

# === ATTICUS BACKEND SETTINGS ===
ATTICUS_BACKGROUND_TASK_INTERVAL = 30

# === CONFIGURATION HELPERS ===
def get_config_value(key: str, default=None):
    """Helper function to get config values with defaults."""
    return globals().get(key, default)

def update_config(key: str, value):
    """Helper function to update config values at runtime (use with caution)."""
    globals()[key] = value

# === ENVIRONMENT-BASED OVERRIDES ===
for key, value in globals().copy().items():
    if key.isupper() and isinstance(value, (str, int, float, bool, list)):
        env_value = os.environ.get(f"ATTICUS_{key}")
        if env_value is not None:
            current_value = globals()[key]
            try:
                if isinstance(current_value, bool):
                    globals()[key] = env_value.lower() in ('true', '1', 'yes', 'on')
                elif isinstance(current_value, int):
                    globals()[key] = int(env_value)
                elif isinstance(current_value, float):
                    globals()[key] = float(env_value)
                elif isinstance(current_value, list):
                    globals()[key] = [item.strip() for item in env_value.split(',')]
                else:
                    globals()[key] = env_value
            except ValueError as e:
                print(f"Warning: Could not cast env var ATTICUS_{key}='{env_value}' to type {type(current_value)}. Error: {e}")
