# sandbox/core/funding_manager.py
import logging
from typing import Dict

logger = logging.getLogger(__name__)

class FundingManager:
    """Simulates the application of funding fees for perpetual futures."""
    
    # CRITICAL FIX: Add the missing class attribute
    FUNDING_INTERVAL_HOURS = 8  # Standard 8-hour funding cycle for most exchanges
    
    def simulate_funding_rate(self, mark_price: float, perp_price: float) -> float:
        """
        Creates a realistic, dynamic funding rate based on the basis (perp vs. mark price).
        A positive rate means longs pay shorts.
        """
        if mark_price == 0: return 0.0
        basis = (perp_price - mark_price) / mark_price
        # A simple model: funding rate is a fraction of the basis.
        # Clamp between -0.5% and +0.5% to keep it realistic.
        funding_rate = max(min(basis * 0.1, 0.005), -0.005)
        return funding_rate

    def apply_funding_fees(self, accounts: Dict, mark_price: float, perp_price: float):
        """
        Applies funding fees to all perpetual positions in all accounts.
        This directly impacts the unrealized P&L of each position.
        """
        funding_rate = self.simulate_funding_rate(mark_price, perp_price)
        if abs(funding_rate) < 1e-6: return # No fees to apply

        logger.info(f"Applying funding rate of {funding_rate:.4%}. Mark: ${mark_price:.2f}, Perp: ${perp_price:.2f}")

        for account in accounts.values():
            for position in account.positions:
                if 'PERP' not in position.symbol: continue # Skip non-perpetual positions

                position_value = abs(position.size) * mark_price
                funding_payment = position_value * funding_rate
                
                # If you are on the paying side of the rate, your P&L decreases.
                if (position.side == 'long' and funding_rate > 0) or \
                   (position.side == 'short' and funding_rate < 0):
                    position.unrealized_pnl -= funding_payment
                else: # Otherwise, you receive the payment.
                    position.unrealized_pnl += funding_payment
