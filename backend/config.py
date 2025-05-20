# backend/config.py

# WebSocket URLs for Exchanges
COINBASE_WS_URL = "wss://ws-feed.pro.coinbase.com"
BINANCE_WS_URL = "wss://stream.binance.com:9443/ws/btcusdt@bookTicker"
OKX_WS_URL = "wss://ws.okx.com:8443/ws/v5/public"

# Symbols/Instruments
COINBASE_PRODUCT_ID = "BTC-USD"
BINANCE_STREAM_SYMBOL = "btcusdt" # for the @bookTicker stream
OKX_INSTRUMENT_ID = "BTC-USDT"

# Dynamic Pricing Parameters
DEFAULT_VOLATILITY = 0.70  # Default annual volatility (e.g., 70%) if not enough data
MIN_VOLATILITY = 0.10      # Minimum annual volatility to use
VOLATILITY_PRICE_HISTORY_SECONDS = 3600 # Look back 1 hour for simple volatility
VOLATILITY_PRICE_UPDATE_INTERVAL_SECONDS = 5 # Assumed interval of price updates for annualization
STRIKE_STEP_PERCENTAGE = 0.0025 # 0.25% step from current price for strikes
STRIKE_ROUNDING_NEAREST = 10 # Round strikes to the nearest $10
NUM_OTM_STRIKES = 2
NUM_ITM_STRIKES = 2
NUM_ATM_STRIKES = 1
OPTION_EXPIRY_MINUTES = 15
RISK_FREE_RATE = 0.01 # Annualized risk-free rate (e.g., 1%)

# WebSocket Server Configuration
WEBSOCKET_SERVER_HOST = "localhost"
WEBSOCKET_SERVER_PORT = 8765
DATA_BROADCAST_INTERVAL_SECONDS = 2 # How often to send updates to frontend

# Logging Configuration
LOG_LEVEL = "INFO" # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# Other platform settings
PLATFORM_NAME = "Atticus"
