# sandbox/utils/black_scholes.py
import math
import logging

logger = logging.getLogger(__name__)

def simple_black_scholes(spot: float, strike: float, time_to_expiry_years: float, 
                        volatility: float, option_type: str) -> float:
    """
    Simple Black-Scholes option pricing implementation.
    
    Args:
        spot: Current asset price
        strike: Option strike price
        time_to_expiry_years: Time to expiry in years
        volatility: Implied volatility (as decimal, e.g., 0.25 for 25%)
        option_type: "call" or "put"
    
    Returns:
        Option premium in USD
    """
    try:
        if spot <= 0 or strike <= 0 or time_to_expiry_years <= 0 or volatility <= 0:
            logger.warning(f"Invalid BS params: S={spot}, K={strike}, T={time_to_expiry_years}, vol={volatility}")
            return 0.0
        
        # Risk-free rate (simplified to 5% annually)
        risk_free_rate = 0.05
        
        # Calculate d1 and d2
        d1 = (math.log(spot / strike) + (risk_free_rate + 0.5 * volatility**2) * time_to_expiry_years) / (volatility * math.sqrt(time_to_expiry_years))
        d2 = d1 - volatility * math.sqrt(time_to_expiry_years)
        
        # Standard normal cumulative distribution function approximation
        def norm_cdf(x):
            """Approximation of standard normal CDF."""
            return 0.5 * (1 + math.erf(x / math.sqrt(2)))
        
        # Calculate option price
        if option_type.lower() == "call":
            price = spot * norm_cdf(d1) - strike * math.exp(-risk_free_rate * time_to_expiry_years) * norm_cdf(d2)
        elif option_type.lower() == "put":
            price = strike * math.exp(-risk_free_rate * time_to_expiry_years) * norm_cdf(-d2) - spot * norm_cdf(-d1)
        else:
            logger.error(f"Invalid option type: {option_type}")
            return 0.0
        
        # Ensure non-negative price
        price = max(price, 0.0)
        
        logger.debug(f"BS: {option_type} S={spot:.2f} K={strike:.2f} T={time_to_expiry_years:.4f} vol={volatility:.4f} => ${price:.2f}")
        return price
        
    except Exception as e:
        logger.error(f"Black-Scholes calculation error: {e}")
        # Fallback: return 2% of spot price as rough estimate
        return spot * 0.02

def calculate_option_greeks(spot: float, strike: float, time_to_expiry_years: float, 
                           volatility: float, option_type: str) -> dict:
    """
    Calculate basic option Greeks.
    
    Returns:
        Dictionary with delta, gamma, theta, vega, rho
    """
    try:
        if time_to_expiry_years <= 0:
            return {"delta": 0, "gamma": 0, "theta": 0, "vega": 0, "rho": 0}
        
        risk_free_rate = 0.05
        
        d1 = (math.log(spot / strike) + (risk_free_rate + 0.5 * volatility**2) * time_to_expiry_years) / (volatility * math.sqrt(time_to_expiry_years))
        d2 = d1 - volatility * math.sqrt(time_to_expiry_years)
        
        def norm_cdf(x):
            return 0.5 * (1 + math.erf(x / math.sqrt(2)))
        
        def norm_pdf(x):
            return math.exp(-0.5 * x**2) / math.sqrt(2 * math.pi)
        
        if option_type.lower() == "call":
            delta = norm_cdf(d1)
        else:  # put
            delta = norm_cdf(d1) - 1
        
        gamma = norm_pdf(d1) / (spot * volatility * math.sqrt(time_to_expiry_years))
        vega = spot * norm_pdf(d1) * math.sqrt(time_to_expiry_years) / 100  # Per 1% vol change
        
        return {
            "delta": delta,
            "gamma": gamma,
            "theta": 0,  # Simplified
            "vega": vega,
            "rho": 0     # Simplified
        }
        
    except Exception as e:
        logger.error(f"Greeks calculation error: {e}")
        return {"delta": 0, "gamma": 0, "theta": 0, "vega": 0, "rho": 0}
