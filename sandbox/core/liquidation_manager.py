# sandbox/core/liquidation_manager.py
from dataclasses import dataclass

@dataclass
class LiquidationCheckResult:
    is_at_risk: bool
    liquidation_price: float

class LiquidationManager:
    """Calculates liquidation prices and checks for liquidation risk."""

    @staticmethod
    def calculate_liquidation_price(entry_price: float, leverage: float, side: str, 
                                    maintenance_margin_rate: float = 0.005) -> float:
        """
        Calculates the estimated liquidation price for a leveraged position.
        Note: Real exchange formulas can be more complex, involving funding rates and fees.
        
        Args:
            maintenance_margin_rate: The margin required to keep the position open (e.g., 0.5%).
        """
        if leverage == 0: return 0.0 if side == 'long' else float('inf')

        # For longs, liquidation occurs when the price drops.
        if side == 'long':
            return entry_price * (1 - (1 / leverage) + maintenance_margin_rate)
        # For shorts, liquidation occurs when the price rises.
        else: # short
            return entry_price * (1 + (1 / leverage) - maintenance_margin_rate)

    @staticmethod
    def check_liquidation(position, mark_price: float) -> LiquidationCheckResult:
        """Checks if a position is at risk of liquidation."""
        liq_price = LiquidationManager.calculate_liquidation_price(
            position.entry_price, position.leverage, position.side
        )
        
        is_at_risk = False
        if position.side == 'long' and mark_price <= liq_price:
            is_at_risk = True
        elif position.side == 'short' and mark_price >= liq_price:
            is_at_risk = True
            
        return LiquidationCheckResult(is_at_risk=is_at_risk, liquidation_price=liq_price)
