from typing import Dict, Optional
from ..strategy_factory import BaseStrategy, StrategyResult
from ...config.sandbox_config import SANDBOX_CONFIG

class ProtectivePutStrategy(BaseStrategy):
    """Implements the protective put hedging strategy."""
    def analyze(self, market_data: Dict, portfolio_summary: Dict) -> Optional[StrategyResult]:
        net_position = portfolio_summary.get("net_position", 0)
        # Strategy applies only if there is a significant long position.
        if net_position <= 0.1:
            return None

        spot_price = market_data.get("btc_price")
        volatility = market_data.get("volatility")
        if not spot_price or not volatility: return None

        # Select an ATM put option as per standard protective put strategy [3].
        strike = spot_price * (1 + SANDBOX_CONFIG.DEFAULT_STRIKE_OFFSETS["ATM"])
        # Use dynamic expiry from SANDBOX_CONFIG
        expiry_hours = SANDBOX_CONFIG.DEFAULT_EXPIRY_HOURS[1]  # Use 4-hour expiry

        cost = self._get_option_price(spot_price, strike, expiry_hours, volatility, 'put')
        
        return StrategyResult(
            strategy_name="Protective Put",
            confidence_score=0.8,
            options_needed=[{"type": "put", "strike": strike, "expiry_hours": expiry_hours, "quantity": net_position, "cost_per_unit": cost}],
            reasoning=f"Protect long position of {net_position:.2f} BTC against downside risk."
        )

class ProtectiveCallStrategy(BaseStrategy):
    """Implements the protective call hedging strategy for short positions."""
    def analyze(self, market_data: Dict, portfolio_summary: Dict) -> Optional[StrategyResult]:
        net_position = portfolio_summary.get("net_position", 0)
        # Strategy applies only if there is a significant short position.
        if net_position >= -0.1:
            return None

        spot_price = market_data.get("btc_price")
        volatility = market_data.get("volatility")
        if not spot_price or not volatility: return None

        strike = spot_price * (1 + SANDBOX_CONFIG.DEFAULT_STRIKE_OFFSETS["ATM"])
        # Use dynamic expiry from SANDBOX_CONFIG
        expiry_hours = SANDBOX_CONFIG.DEFAULT_EXPIRY_HOURS[1]  # Use 4-hour expiry

        cost = self._get_option_price(spot_price, strike, expiry_hours, volatility, 'call')
        
        return StrategyResult(
            strategy_name="Protective Call",
            confidence_score=0.8,
            options_needed=[{"type": "call", "strike": strike, "expiry_hours": expiry_hours, "quantity": abs(net_position), "cost_per_unit": cost}],
            reasoning=f"Protect short position of {abs(net_position):.2f} BTC against upside risk (short squeeze)."
        )
