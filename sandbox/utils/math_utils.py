import numpy as np
import math
from scipy.stats import norm

def black_scholes_price(spot, strike, time_to_expiry, risk_free_rate, volatility, option_type):
    if time_to_expiry <= 0: return max(0, spot - strike) if option_type == 'call' else max(0, strike - spot)
    d1 = (math.log(spot / strike) + (risk_free_rate + 0.5 * volatility**2) * time_to_expiry) / (volatility * math.sqrt(time_to_expiry))
    d2 = d1 - volatility * math.sqrt(time_to_expiry)
    if option_type == 'call':
        price = spot * norm.cdf(d1) - strike * math.exp(-risk_free_rate * time_to_expiry) * norm.cdf(d2)
    else:
        price = strike * math.exp(-risk_free_rate * time_to_expiry) * norm.cdf(-d2) - spot * norm.cdf(-d1)
    return max(0, price)

def calculate_realized_volatility(prices: list, trading_periods_per_year=252):
    if len(prices) < 2: return 0.0
    log_returns = np.log(np.array(prices)[1:] / np.array(prices)[:-1])
    return np.std(log_returns) * np.sqrt(trading_periods_per_year)
