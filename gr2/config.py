# gr2/config.py
# Screen-State Schema for Golden Retriever 2.0

from typing import Dict, Any, Union, List
import logging

logger = logging.getLogger(__name__)

# System prompt for the LLM
SYSTEM_PROMPT = """
You are a friendly BTC-options coach.

When you define a term, include a simple analogy
(e.g. "A put is like return insurance on a gadget…").

Never mention Greeks unless the retrieved context
explicitly contains a Greek term.
"""

# Greek terms for filtering
GREEK_TERMS = {"delta", "gamma", "theta", "vega", "rho"}

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
        "title": "Delta - Price Sensitivity",
        "content": "Delta measures how much an option's price changes when the underlying asset (Bitcoin) moves by $1. A delta of 0.5 means the option price moves $0.50 when Bitcoin moves $1.00. Think of delta as the 'speedometer' of your option - it tells you how fast your position changes with market moves.",
        "topic": "greeks"
    },
    {
        "title": "Gamma - Acceleration",
        "content": "Gamma measures how much delta changes when the underlying asset moves. It's highest for at-the-money options and decreases as options move in or out of the money. Gamma is like the 'accelerator' - it tells you how quickly your delta (and thus your position sensitivity) changes.",
        "topic": "greeks"
    },
    {
        "title": "Theta - Time Decay",
        "content": "Theta measures how much an option's value decreases as time passes. Options lose value as they approach expiration, even if the underlying asset doesn't move. Think of theta as the 'ticking clock' - every day that passes, your option becomes slightly less valuable.",
        "topic": "greeks"
    },
    {
        "title": "Vega - Volatility Sensitivity",
        "content": "Vega measures how much an option's price changes when implied volatility changes by 1%. Higher volatility generally means higher option prices. Vega is like the 'weather forecast' - it tells you how much your option value changes when market uncertainty (volatility) changes.",
        "topic": "greeks"
    },
    {
        "title": "Call Options Basics",
        "content": "A call option gives you the right to buy Bitcoin at a specific price (strike) before expiration. You buy calls when you expect Bitcoin to rise. Think of a call like a reservation at a restaurant - you pay a small fee now to lock in the right to buy at today's price, even if prices go up later.",
        "topic": "basics"
    },
    {
        "title": "Put Options Basics",
        "content": "A put option gives you the right to sell Bitcoin at a specific price (strike) before expiration. You buy puts when you expect Bitcoin to fall. Think of a put like insurance on your Bitcoin - you pay a premium now to protect against price drops, like car insurance protects against accidents.",
        "topic": "basics"
    },
    {
        "title": "Strike Price Selection",
        "content": "The strike price is the price at which you can buy (call) or sell (put) Bitcoin. At-the-money (ATM) strikes are closest to current Bitcoin price. In-the-money (ITM) options have intrinsic value, while out-of-the-money (OTM) options are cheaper but riskier. Choose based on your market outlook and risk tolerance.",
        "topic": "strategy"
    },
    {
        "title": "Expiration Timeframes",
        "content": "Options expire at specific times. Shorter expirations (minutes to hours) are cheaper but decay faster. Longer expirations (days to weeks) cost more but give you more time for your prediction to be right. Choose expiration based on when you expect your market move to happen.",
        "topic": "basics"
    },
    {
        "title": "Premium and Pricing",
        "content": "Option premium is the price you pay for the option. It consists of intrinsic value (if any) plus time value. Premiums are higher for longer expirations and when volatility is high. The premium is your maximum loss when buying options - you can't lose more than what you paid.",
        "topic": "basics"
    },
    {
        "title": "Risk Management",
        "content": "Never risk more than you can afford to lose. Options can expire worthless, so only use money you're comfortable losing. Consider position sizing - don't put all your capital in one trade. Use stop-losses or position limits to manage risk. Remember: options are leverage, so small market moves can create large gains or losses.",
        "topic": "strategy"
    }
]

# Confidence thresholds for fallback
CONFIDENCE_THRESHOLD = 0.3
MIN_RETRIEVED_DOCS = 1 