# dynamic_pricing.py
import numpy as np
from scipy.stats import norm
from math import log, sqrt, exp, erf # erf for Black-Scholes CDF
import time

# --- Black-Scholes Model ---
# S: Current price of the underlying asset (e.g., BTC from Coinbase)
# K: Strike price
# T: Time to expiration (in years)
# r: Risk-free interest rate (annualized)
# sigma: Volatility of the underlying asset (annualized)

def N(x):
    """ Cumulative standard normal distribution function """
    return (1.0 + erf(x / sqrt(2.0))) / 2.0

def black_scholes_premium(S, K, T, r, sigma, option_type='call'):
    if S <= 0 or K <= 0 or T <= 0 or sigma <= 0: # Basic validation
        # For ultra-short options, T will be very small but positive
        # Sigma must be positive
        if sigma <=0: sigma = 0.00001 # Avoid division by zero if sigma is bad
        if T <= 0: T = 0.0000001 # Avoid division by zero if T is bad

    d1 = (log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * sqrt(T))
    d2 = d1 - sigma * sqrt(T)

    if option_type.lower() == 'call':
        premium = S * N(d1) - K * exp(-r * T) * N(d2)
    elif option_type.lower() == 'put':
        premium = K * exp(-r * T) * N(-d2) - S * N(-d1)
    else:
        raise ValueError("Invalid option_type. Use 'call' or 'put'.")
    return max(premium, 0.00000001) # Ensure premium is not zero or negative for display
*Reference: [5], [9]*

# --- Volatility Calculation ---
# For a demo, we might start with a fixed volatility or a very simple historical one.
# Real-world: Implied Volatility from existing options markets or sophisticated HV.
VOLATILITY_WINDOW_SECONDS = 15 * 60 # 15 minutes for short-term vol
price_history = [] # Store recent prices (e.g., from Coinbase last trade)

def update_price_history(current_price):
    global price_history
    price_history.append(current_price)
    # Keep history to a manageable size, e.g., last hour for 15-min vol
    max_history_len = int((60 * 60) / 5) # Assuming price updates every 5 seconds, store 1 hr
    if len(price_history) > max_history_len:
        price_history = price_history[-max_history_len:]

def calculate_simple_historical_volatility():
    global price_history
    if len(price_history) < 20: # Need enough data points
        return 0.70 # Default annual volatility (e.g., 70%) if not enough data
    
    log_returns = np.log(np.array(price_history[1:]) / np.array(price_history[:-1]))
    
    # Annualize based on assumption of price updates (e.g., every 5 seconds)
    # Number of 5-second intervals in a year = (365 * 24 * 60 * 60) / 5
    annualization_factor = sqrt((365 * 24 * 60 * 60) / 5) # Adjust '5' if price updates differ
    std_dev = np.std(log_returns)
    volatility = std_dev * annualization_factor
    return max(volatility, 0.1) # Ensure volatility is not too low (e.g., min 10%)

# --- Strike Price Generation ---
def generate_dynamic_strikes(current_btc_price, num_otm=2, num_itm=2, num_atm=1):
    """ Generates ITM, ATM, OTM strikes dynamically. """
    strikes = {}
    # For 15-min options, strikes should be relatively tight.
    # Adjust increment based on typical 15-min BTC price movement.
    # Let's say a 0.25% - 0.5% step from current price.
    step_percentage = 0.0025 # 0.25%
    atm_strike = round(current_btc_price / 10) * 10 # Round to nearest $10 for ATM

    strikes['atm'] = [atm_strike]
    strikes['itm_call'] = [round((atm_strike - (i+1) * (current_btc_price * step_percentage))/10)*10 for i in range(num_itm)]
    strikes['otm_call'] = [round((atm_strike + (i+1) * (current_btc_price * step_percentage))/10)*10 for i in range(num_otm)]
    
    strikes['itm_put'] = [round((atm_strike + (i+1) * (current_btc_price * step_percentage))/10)*10 for i in range(num_itm)]
    strikes['otm_put'] = [round((atm_strike - (i+1) * (current_btc_price * step_percentage))/10)*10 for i in range(num_otm)]
    
    return strikes
*Reference: [6]*

# --- Option Chain Generation ---
EXPIRY_MINUTES = 15
RISK_FREE_RATE = 0.01 # Annualized (e.g., 1%) - for short expiries, its impact is small

def get_option_chain(current_btc_price):
    if current_btc_price is None or current_btc_price <= 0:
        return []
        
    update_price_history(current_btc_price)
    volatility = calculate_simple_historical_volatility()
    
    # Time to expiration in years for a 15-minute option
    T = (EXPIRY_MINUTES / (60 * 24 * 365))

    dynamic_strikes = generate_dynamic_strikes(current_btc_price)
    
    option_chain = []

    # ATM options
    for strike in dynamic_strikes['atm']:
        call_premium = black_scholes_premium(current_btc_price, strike, T, RISK_FREE_RATE, volatility, 'call')
        put_premium = black_scholes_premium(current_btc_price, strike, T, RISK_FREE_RATE, volatility, 'put')
        option_chain.append({'type': 'call', 'strike': strike, 'premium': call_premium, 'moneyness': 'ATM'})
        option_chain.append({'type': 'put', 'strike': strike, 'premium': put_premium, 'moneyness': 'ATM'})

    # ITM Calls / OTM Puts
    for strike in dynamic_strikes['itm_call']: # Lower strikes
        call_premium = black_scholes_premium(current_btc_price, strike, T, RISK_FREE_RATE, volatility, 'call')
        put_premium = black_scholes_premium(current_btc_price, strike, T, RISK_FREE_RATE, volatility, 'put')
        option_chain.append({'type': 'call', 'strike': strike, 'premium': call_premium, 'moneyness': 'ITM'})
        option_chain.append({'type': 'put', 'strike': strike, 'premium': put_premium, 'moneyness': 'OTM'})

    # OTM Calls / ITM Puts
    for strike in dynamic_strikes['otm_call']: # Higher strikes
        call_premium = black_scholes_premium(current_btc_price, strike, T, RISK_FREE_RATE, volatility, 'call')
        put_premium = black_scholes_premium(current_btc_price, strike, T, RISK_FREE_RATE, volatility, 'put')
        option_chain.append({'type': 'call', 'strike': strike, 'premium': call_premium, 'moneyness': 'OTM'})
        option_chain.append({'type': 'put', 'strike': strike, 'premium': put_premium, 'moneyness': 'ITM'})
        
    return sorted(option_chain, key=lambda x: (x['type'], x['strike']))
