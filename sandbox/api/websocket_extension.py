# sandbox/api/websocket_extension.py
import logging
import asyncio
from typing import Dict, Any, Optional, Tuple

from ..core.synthetic_position_manager import SyntheticPositionManager
from ..core.risk_engine import RiskEngine
from ..hedging.hedging_engine import HedgingEngine
from ..config.sandbox_config import SANDBOX_CONFIG

logger = logging.getLogger(__name__)

class SandboxService:
    """
    The sandbox service now reads data non-invasively from the central DataHub.
    """
    def __init__(self, data_hub: Any, pricing_engine: Any):
        self.data_hub = data_hub
        self.pricing_engine = pricing_engine
        self.position_manager = SyntheticPositionManager()
        self.risk_engine = RiskEngine(self.position_manager)
        self.hedging_engine = HedgingEngine(self.pricing_engine)
        self.is_running = False
        logger.info("SandboxService initialized and configured to read from Data Hub.")

    async def _background_tasks_loop(self):
        """The internal processing loop for continuous analysis."""
        logger.info("Sandbox background tasks loop started.")
        while self.is_running:
            try:
                # Get the latest price from the data feed manager
                mark_price = self.data_hub.get_current_price()
                
                if mark_price and mark_price > 0:
                    perp_price = mark_price * 1.0001
                    self.position_manager.update_pnl_and_funding(mark_price, perp_price)

                await asyncio.sleep(SANDBOX_CONFIG.HEDGING_CHECK_INTERVAL_SECONDS)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in sandbox background loop: {e}", exc_info=True)

    def start(self):
        if not self.is_running:
            self.is_running = True
            asyncio.create_task(self._background_tasks_loop())

    def stop(self):
        self.is_running = False
        logger.info("SandboxService stopping.")

    async def get_current_analysis(self) -> Dict:
        """Generates the full sandbox data packet on demand for broadcasting."""
        mark_price = self.data_hub.get_current_price()
        volatility = getattr(self.pricing_engine, 'current_volatility', 0.25)
        
        portfolio_summary = self.position_manager.get_portfolio_summary()
        risk_analysis = self.risk_engine.analyze_risk(mark_price)
        
        hedging_market_data = {"btc_price": mark_price, "volatility": volatility}
        hedging_plan = self.hedging_engine.devise_hedging_plan(hedging_market_data, portfolio_summary)
        
        # Include available expiry times from SANDBOX_CONFIG
        available_expiries = SANDBOX_CONFIG.DEFAULT_EXPIRY_HOURS
        
        return {
            "is_running": self.is_running,
            "portfolio_summary": portfolio_summary,
            "risk_analysis": risk_analysis,
            "hedging_plan": hedging_plan.__dict__ if hedging_plan else None,
            "current_mark_price": mark_price,
            "available_expiries": available_expiries
        }

    async def execute_sandbox_trade(self, trade_data: Dict) -> Tuple[bool, str, Optional[Dict]]:
        """Execute a trade in the sandbox environment and update all necessary components."""
        try:
            # Get current market price
            current_price = self.data_hub.get_current_price()
            
            if current_price <= 0:
                return False, "Invalid market price", None

            # Map side for synthetic position
            position_side = 'long' if trade_data["side"] == "buy" else 'short'
            # Create synthetic position
            position = self.position_manager.add_position(
                account_id=trade_data["user_id"],
                pos_data={
                    'symbol': trade_data["symbol"],
                    'size': trade_data["quantity"],
                    'entry_price': current_price,
                    'side': position_side,
                    'leverage': 1.0,
                    'order_type': 'taker'
                }
            )

            # Update portfolio summary
            portfolio_summary = self.position_manager.get_portfolio_summary()
            
            # Update risk analysis
            risk_analysis = self.risk_engine.analyze_risk(current_price)
            
            # Generate new hedging plan
            hedging_market_data = {
                "btc_price": current_price,
                "volatility": getattr(self.pricing_engine, 'current_volatility', 0.25)
            }
            hedging_plan = self.hedging_engine.devise_hedging_plan(hedging_market_data, portfolio_summary)

            # Return success with updated data
            return True, "Trade executed successfully", {
                "position": position,
                "portfolio_summary": portfolio_summary,
                "risk_analysis": risk_analysis,
                "hedging_plan": hedging_plan.__dict__ if hedging_plan else None
            }

        except Exception as e:
            logger.error(f"Error executing sandbox trade: {e}", exc_info=True)
            return False, f"Trade execution failed: {str(e)}", None
