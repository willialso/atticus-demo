# gr2/config.py
# Screen-State Schema for Golden Retriever 2.0

from typing import Dict, Any, Union, List

SCREEN_SCHEMA = {
    "current_btc_price": float,
    "selected_option_type": str,        # "call" | "put" | None
    "selected_strike": Union[float, None],
    "selected_expiry": int,             # days/minutes
    "visible_strikes": List[float],     # strikes rendered in chain
    "active_tab": str,                  # "options_chain", "portfolio", "trading", etc.
}

# BTC Options Knowledge Base for v1 scope
BTC_OPTIONS_KB = [
    {
        "id": "delta",
        "title": "Delta",
        "content": "Delta shows how much the option price is expected to move for a $1 move in BTC. For calls, delta ranges from 0 to 1. For puts, delta ranges from -1 to 0. ATM options have delta around 0.5 for calls and -0.5 for puts."
    },
    {
        "id": "gamma",
        "title": "Gamma", 
        "content": "Gamma measures the rate of change in delta as the underlying BTC price changes. It's highest for ATM options and decreases as options move ITM or OTM. Gamma represents the 'acceleration' of option price changes."
    },
    {
        "id": "theta",
        "title": "Theta",
        "content": "Theta measures the time decay of an option's value. It shows how much the option loses value each day as it approaches expiration. Theta is typically negative (time decay) and accelerates as expiration approaches."
    },
    {
        "id": "vega",
        "title": "Vega",
        "content": "Vega measures the sensitivity of an option's price to changes in implied volatility. Higher vega means the option price is more sensitive to volatility changes. Vega is highest for ATM options and decreases for ITM/OTM options."
    },
    {
        "id": "strike_selection",
        "title": "Strike Selection",
        "content": "If no strike is chosen, the UI suggests the nearest ATM (At-The-Money) strike. ATM strikes have strike prices closest to the current BTC price. ITM (In-The-Money) strikes are below current price for calls and above for puts. OTM (Out-of-The-Money) strikes are above current price for calls and below for puts."
    },
    {
        "id": "moneyness",
        "title": "Moneyness",
        "content": "Moneyness describes the relationship between the strike price and current BTC price. ITM (In-The-Money) options have intrinsic value. ATM (At-The-Money) options have strike prices near the current price. OTM (Out-of-The-Money) options have no intrinsic value but may have time value."
    },
    {
        "id": "premium_calculation",
        "title": "Premium Calculation",
        "content": "Option premium consists of intrinsic value (for ITM options) plus time value. The Black-Scholes model calculates fair value based on current price, strike, time to expiry, volatility, and risk-free rate. Premium is paid in BTC but displayed in USD for convenience."
    },
    {
        "id": "expiry_times",
        "title": "Expiry Times",
        "content": "Available expiry times are 2-Hour, 4-Hour, 8-Hour, and 12-Hour. Shorter expiries have higher theta (time decay) and lower vega (volatility sensitivity). Choose expiry based on your market outlook and risk tolerance."
    },
    {
        "id": "option_types",
        "title": "Option Types",
        "content": "Calls give the right to buy BTC at the strike price. Puts give the right to sell BTC at the strike price. Calls profit when BTC rises above strike + premium. Puts profit when BTC falls below strike - premium."
    },
    {
        "id": "risk_management",
        "title": "Risk Management",
        "content": "Long options have limited risk (premium paid) and unlimited profit potential. Short options have unlimited risk and limited profit (premium received). Always consider position sizing and portfolio diversification."
    }
]

# Confidence thresholds for fallback
CONFIDENCE_THRESHOLD = 0.25
MIN_RETRIEVED_DOCS = 1 