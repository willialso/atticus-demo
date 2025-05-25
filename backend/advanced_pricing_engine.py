# backend/advanced_pricing_engine.py

import numpy as np
import pandas as pd
import math
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from scipy.stats import norm
from backend import config
from backend.volatility_engine import AdvancedVolatilityEngine
from backend.alpha_signals import AlphaSignalGenerator
from backend.utils import setup_logger

logger = setup_logger(__name__)

# --- Data Classes for Option Quotes and Chains ---
@dataclass
class OptionQuote:
    symbol: str
    option_type: str  # "call" or "put"
    strike: float
    expiry_minutes: int
    expiry_label: str
    premium_usd: float  # Premium per contract (for 0.01 BTC underlying)
    premium_btc: float  # Premium in BTC terms for the contract
    delta: float  # Scaled for contract size
    gamma: float  # Scaled for contract size
    theta: float  # Scaled for contract size (per day, USD value change)
    vega: float  # Scaled for contract size (per 1% vol change, USD value change)
    implied_vol: float  # Annualized volatility used for this quote's calculation
    moneyness: str  # "ITM", "ATM", "OTM"

    def dict(self):
        return asdict(self)

@dataclass
class OptionChain:
    underlying_price: float
    timestamp: float
    expiry_minutes: int
    expiry_label: str
    calls: List[OptionQuote]
    puts: List[OptionQuote]
    volatility_used: float
    alpha_adjustment_applied: bool

    def dict(self):
        return {
            "underlying_price": self.underlying_price,
            "timestamp": self.timestamp,
            "expiry_minutes": self.expiry_minutes,
            "expiry_label": self.expiry_label,
            "calls": [c.dict() for c in self.calls],
            "puts": [p.dict() for p in self.puts],
            "volatility_used": self.volatility_used,
            "alpha_adjustment_applied": self.alpha_adjustment_applied
        }

# --- Main Pricing Engine Class ---
class AdvancedPricingEngine:
    """
    Advanced Black-Scholes pricing engine with critical fixes for mini-contracts.
    """

    def __init__(self, volatility_engine: AdvancedVolatilityEngine, alpha_signal_generator: AlphaSignalGenerator):
        self.vol_engine = volatility_engine
        self.alpha_generator = alpha_signal_generator
        self.current_price = 0.0
        logger.info("AdvancedPricingEngine initialized with CRITICAL FIXES applied.")

    def update_market_data(self, price: float, volume: float = 0) -> None:
        """Updates the engine with the latest market price and volume."""
        if price <= 0:
            return

        self.current_price = price

        if hasattr(self.vol_engine, 'update_price') and callable(getattr(self.vol_engine, 'update_price')):
            self.vol_engine.update_price(price)

        if hasattr(self.alpha_generator, 'update_tick') and callable(getattr(self.alpha_generator, 'update_tick')):
            self.alpha_generator.update_tick(price, volume)

    @staticmethod
    def black_scholes_with_greeks(S: float, K: float, T: float, r: float,
                                 sigma: float, option_type: str) -> Tuple[float, Dict[str, float]]:
        """
        Calculates Black-Scholes option price and Greeks.
        *** ENHANCED with better error handling for mini-contracts ***
        """
        # Input validation
        if S <= 0 or K <= 0 or T <= 0:
            return 0.0, {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0}

        # Floor sigma for stability
        if sigma <= 1e-6:
            sigma = 1e-4

        try:
            # Floor T for extreme short expiries
            if T < 1e-9:
                T = 1e-9

            # Standard Black-Scholes calculations
            d1_numerator = math.log(S / K) + (r + 0.5 * sigma ** 2) * T
            d1_denominator = sigma * math.sqrt(T)

            if d1_denominator == 0:
                # Handle extreme cases
                price_at_extremes = 0.0
                if option_type.lower() == "call":
                    price_at_extremes = max(0, S - K)
                elif option_type.lower() == "put":
                    price_at_extremes = max(0, K - S)
                
                # *** CRITICAL FIX: Proper delta for extreme cases ***
                delta_extreme = 0.0
                if option_type.lower() == "call" and S > K:
                    delta_extreme = 1.0
                elif option_type.lower() == "put" and K > S:
                    delta_extreme = -1.0
                
                return price_at_extremes, {
                    "delta": delta_extreme, 
                    "gamma": 0.0, 
                    "theta": 0.0, 
                    "vega": 0.0
                }

            d1 = d1_numerator / d1_denominator
            d2 = d1 - sigma * math.sqrt(T)

            # Option price calculation
            if option_type.lower() == "call":
                price = S * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
                delta = norm.cdf(d1)
            elif option_type.lower() == "put":
                price = K * math.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
                delta = norm.cdf(d1) - 1
            else:
                raise ValueError("option_type must be 'call' or 'put'")

            # Greeks calculations
            gamma_val = norm.pdf(d1) / (S * sigma * math.sqrt(T)) if S > 0 and sigma > 0 and T > 0 else 0.0

            theta_term1 = -(S * norm.pdf(d1) * sigma) / (2 * math.sqrt(T)) if T > 0 and sigma > 0 else 0.0
            if option_type.lower() == "call":
                theta_term2 = -r * K * math.exp(-r * T) * norm.cdf(d2)
            else:
                theta_term2 = r * K * math.exp(-r * T) * norm.cdf(-d2)

            theta_annual = theta_term1 + theta_term2
            theta_per_day = theta_annual / 365.25

            vega_val = S * norm.pdf(d1) * math.sqrt(T) if T > 0 else 0.0
            vega_per_1_pct_vol_change = vega_val / 100.0

            greeks = {
                "delta": delta,
                "gamma": gamma_val,
                "theta": theta_per_day,
                "vega": vega_per_1_pct_vol_change
            }

            return max(price, 1e-8), greeks

        except (ValueError, ZeroDivisionError, OverflowError) as e:
            logger.error(f"Black-Scholes calculation error: S={S}, K={K}, T={T}, sigma={sigma}: {e}")
            return 1e-8, {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0}

    def generate_strikes_for_expiry(self, expiry_minutes: int) -> List[float]:
        """Generates strike prices for a given expiry duration."""
        if self.current_price <= 0:
            logger.warning(f"Cannot generate strikes: current_price is invalid ({self.current_price}).")
            return []

        strike_params = config.STRIKE_RANGES_BY_EXPIRY.get(
            expiry_minutes,
            config.STRIKE_RANGES_BY_EXPIRY.get(15)
        )

        if strike_params is None:
            logger.error(f"No strike parameters found for expiry {expiry_minutes}.")
            return []

        num_itm_strikes = strike_params["num_itm"]
        num_otm_strikes = strike_params["num_otm"]
        step_percentage = strike_params["step_pct"]
        rounding_val = config.STRIKE_ROUNDING_NEAREST

        generated_strikes = set()

        # ATM strike
        atm_strike_price = round(self.current_price / rounding_val) * rounding_val
        if atm_strike_price <= 0:
            atm_strike_price = rounding_val
        generated_strikes.add(atm_strike_price)

        # Step value proportional to current price
        actual_step_value = atm_strike_price * step_percentage

        # ITM strikes
        for i in range(1, num_itm_strikes + 1):
            itm_k_val = round((atm_strike_price - i * actual_step_value) / rounding_val) * rounding_val
            if itm_k_val > 0:
                generated_strikes.add(itm_k_val)

        # OTM strikes
        for i in range(1, num_otm_strikes + 1):
            otm_k_val = round((atm_strike_price + i * actual_step_value) / rounding_val) * rounding_val
            generated_strikes.add(otm_k_val)

        positive_strikes = sorted([s for s in generated_strikes if s > 0])
        
        if not positive_strikes:
            logger.warning(f"No positive strikes generated for {expiry_minutes}min.")
        
        return positive_strikes

    def classify_moneyness(self, strike: float, option_type: str) -> str:
        """
        *** CRITICAL FIX: Optimal moneyness classification ***
        Using 0.5% threshold for accurate ITM/ATM/OTM classification.
        """
        if self.current_price <= 0:
            return "N/A"

        # *** CRITICAL FIX: Set to optimal 0.5% threshold ***
        atm_threshold_percentage = 0.005  # 0.5% around current price is considered ATM
        
        lower_atm_bound = self.current_price * (1 - atm_threshold_percentage)
        upper_atm_bound = self.current_price * (1 + atm_threshold_percentage)

        if option_type.lower() == "call":
            if strike < lower_atm_bound:
                return "ITM"
            elif strike > upper_atm_bound:
                return "OTM"
            else:
                return "ATM"
        elif option_type.lower() == "put":
            if strike > upper_atm_bound:
                return "ITM"
            elif strike < lower_atm_bound:
                return "OTM"
            else:
                return "ATM"
        
        return "N/A"

    def apply_alpha_adjustment(self, base_premium_usd_on_contract: float, option_type: str,
                             moneyness_status: str, expiry_minutes: int) -> Tuple[float, float]:
        """Applies alpha signal adjustments to the base premium."""
        if not config.ALPHA_SIGNALS_ENABLED:
            return base_premium_usd_on_contract, 0.0

        try:
            primary_alpha_signal = self.alpha_generator.generate_primary_signal()
            
            if not (primary_alpha_signal and hasattr(primary_alpha_signal, 'value') and hasattr(primary_alpha_signal, 'confidence')):
                return base_premium_usd_on_contract, 0.0

            base_adjustment_percentage = 0.05
            signal_confidence_weight = primary_alpha_signal.confidence

            signal_value_effect = 0.0
            if option_type.lower() == "call":
                signal_value_effect = primary_alpha_signal.value
            elif option_type.lower() == "put":
                signal_value_effect = -primary_alpha_signal.value

            total_adjustment_factor = signal_value_effect * signal_confidence_weight * base_adjustment_percentage

            if moneyness_status == "OTM":
                total_adjustment_factor *= 1.5
            elif moneyness_status == "ATM":
                total_adjustment_factor *= 1.2

            adjusted_premium_val = base_premium_usd_on_contract * (1 + total_adjustment_factor)
            min_premium_floor_val = max(base_premium_usd_on_contract * 0.5, 1e-5 * config.STANDARD_CONTRACT_SIZE_BTC)
            final_adjusted_premium_val = max(adjusted_premium_val, min_premium_floor_val)

            actual_adjustment_factor_applied = (final_adjusted_premium_val / base_premium_usd_on_contract) - 1 if base_premium_usd_on_contract > 0 else 0.0

            return final_adjusted_premium_val, actual_adjustment_factor_applied

        except Exception as e_alpha:
            logger.error(f"Alpha adjustment error: {e_alpha}")
            return base_premium_usd_on_contract, 0.0

    def generate_option_chain(self, expiry_minutes: int) -> Optional[OptionChain]:
        """
        *** ENHANCED with critical fixes for mini-contracts ***
        """
        if self.current_price <= 0:
            logger.warning(f"Cannot generate option chain: No valid current_price ({self.current_price}).")
            return None

        try:
            # Get volatility
            annualized_sigma = self.vol_engine.get_expiry_adjusted_volatility(expiry_minutes)
            
            if not (config.MIN_VOLATILITY <= annualized_sigma <= config.MAX_VOLATILITY):
                logger.warning(f"Volatility {annualized_sigma:.4f} outside range. Clamping.")
                annualized_sigma = max(config.MIN_VOLATILITY, min(annualized_sigma, config.MAX_VOLATILITY))

            # *** CRITICAL DEBUG LOGGING ***
            logger.info(f"Generating chain for {expiry_minutes}min: BTC=${self.current_price:.2f}, "
                       f"Sigma={annualized_sigma:.4f}, Contract_Size={config.STANDARD_CONTRACT_SIZE_BTC}")

            # Generate strikes
            strike_prices_list = self.generate_strikes_for_expiry(expiry_minutes)
            if not strike_prices_list:
                logger.warning(f"No strikes generated for {expiry_minutes}min.")
                return None

            # Time to expiry in years
            time_to_expiry_years = expiry_minutes / (60 * 24 * 365.25)

            call_quotes_list: List[OptionQuote] = []
            put_quotes_list: List[OptionQuote] = []
            last_alpha_adj_factor_summary = 0.0

            # Process each strike and option type
            for K_strike in strike_prices_list:
                for option_contract_type in ["call", "put"]:
                    
                    # Calculate base premium per unit of underlying
                    base_premium_per_unit, greeks_per_unit = self.black_scholes_with_greeks(
                        S=self.current_price, K=K_strike, T=time_to_expiry_years,
                        r=config.RISK_FREE_RATE, sigma=annualized_sigma, option_type=option_contract_type
                    )

                    # Calculate intrinsic value per unit
                    intrinsic_value_per_unit = 0.0
                    if option_contract_type == "call":
                        intrinsic_value_per_unit = max(0, self.current_price - K_strike)
                    else:  # put
                        intrinsic_value_per_unit = max(0, K_strike - self.current_price)

                    # *** CRITICAL FIX: Enforce intrinsic value floor ***
                    if base_premium_per_unit < intrinsic_value_per_unit:
                        logger.debug(f"BS premium ${base_premium_per_unit:.4f} below intrinsic ${intrinsic_value_per_unit:.4f} for {K_strike} {option_contract_type}")
                        base_premium_per_unit = intrinsic_value_per_unit

                    # *** CRITICAL FIX: Scale by CORRECT contract size (0.01 BTC) ***
                    base_premium_usd_for_contract = base_premium_per_unit * config.STANDARD_CONTRACT_SIZE_BTC

                    # Classify moneyness with improved threshold
                    option_moneyness = self.classify_moneyness(K_strike, option_contract_type)

                    # Apply alpha adjustments
                    adjusted_premium_usd_for_contract, alpha_adjustment_factor = self.apply_alpha_adjustment(
                        base_premium_usd_for_contract, option_contract_type, option_moneyness, expiry_minutes
                    )

                    if config.ALPHA_SIGNALS_ENABLED:
                        last_alpha_adj_factor_summary = alpha_adjustment_factor

                    # Convert to BTC premium
                    final_premium_btc_for_contract = adjusted_premium_usd_for_contract / self.current_price if self.current_price > 0 else 0.0

                    # *** CRITICAL FIX #3: Scale Greeks for contract size AND enforce ITM delta floors ***
                    scaled_greeks_values = {
                        greek_name: greek_value * config.STANDARD_CONTRACT_SIZE_BTC
                        for greek_name, greek_value in greeks_per_unit.items()
                    }

                    # *** CRITICAL FIX #4: Enforce proper delta floors for ITM options ***
                    if option_moneyness == "ITM":
                        if option_contract_type == "call":
                            # ITM calls should have delta close to 1.0 (scaled by contract size)
                            min_delta = 0.7 * config.STANDARD_CONTRACT_SIZE_BTC
                            scaled_greeks_values["delta"] = max(scaled_greeks_values["delta"], min_delta)
                        else:  # ITM puts
                            # ITM puts should have delta close to -1.0 (scaled by contract size) 
                            max_delta = -0.7 * config.STANDARD_CONTRACT_SIZE_BTC
                            scaled_greeks_values["delta"] = min(scaled_greeks_values["delta"], max_delta)

                    # *** CRITICAL DEBUG LOGGING ***
                    logger.debug(f"Strike {K_strike} {option_contract_type}: "
                               f"Intrinsic=${intrinsic_value_per_unit:.4f}, "
                               f"BS_Premium=${base_premium_per_unit:.4f}, "
                               f"Contract_Premium=${adjusted_premium_usd_for_contract:.2f}, "
                               f"Delta={scaled_greeks_values['delta']:.4f}, "
                               f"Moneyness={option_moneyness}")

                    # Create option quote
                    option_quote_obj = OptionQuote(
                        symbol=f"BTC-{config.EXPIRY_LABELS.get(expiry_minutes, str(expiry_minutes)+'M')}-{int(K_strike)}-{option_contract_type[0].upper()}",
                        option_type=option_contract_type,
                        strike=K_strike,
                        expiry_minutes=expiry_minutes,
                        expiry_label=config.EXPIRY_LABELS.get(expiry_minutes, f"{expiry_minutes}min"),
                        premium_usd=round(adjusted_premium_usd_for_contract, 2),
                        premium_btc=round(final_premium_btc_for_contract, 8),
                        delta=round(scaled_greeks_values["delta"], 4),
                        gamma=round(scaled_greeks_values["gamma"], 6),
                        theta=round(scaled_greeks_values["theta"], 4),
                        vega=round(scaled_greeks_values["vega"], 4),
                        implied_vol=annualized_sigma,
                        moneyness=option_moneyness
                    )

                    if option_contract_type == "call":
                        call_quotes_list.append(option_quote_obj)
                    else:
                        put_quotes_list.append(option_quote_obj)

            # Sort by strike price
            call_quotes_list.sort(key=lambda q: q.strike)
            put_quotes_list.sort(key=lambda q: q.strike)

            return OptionChain(
                underlying_price=self.current_price,
                timestamp=pd.Timestamp.now(tz='UTC').timestamp(),
                expiry_minutes=expiry_minutes,
                expiry_label=config.EXPIRY_LABELS.get(expiry_minutes, f"{expiry_minutes}min"),
                calls=call_quotes_list,
                puts=put_quotes_list,
                volatility_used=annualized_sigma,
                alpha_adjustment_applied=config.ALPHA_SIGNALS_ENABLED
            )

        except Exception as e_chain_gen:
            logger.error(f"Option chain generation error for {expiry_minutes}min: {e_chain_gen}", exc_info=True)
            return None

    def generate_all_chains(self) -> Dict[int, Optional[OptionChain]]:
        """Generates option chains for all configured expiries."""
        all_generated_chains: Dict[int, Optional[OptionChain]] = {}

        for expiry_duration_minutes in config.AVAILABLE_EXPIRIES_MINUTES:
            chain = self.generate_option_chain(expiry_duration_minutes)
            all_generated_chains[expiry_duration_minutes] = chain
            
            if not chain:
                logger.warning(f"Failed to generate chain for expiry: {expiry_duration_minutes} minutes.")

        return all_generated_chains
