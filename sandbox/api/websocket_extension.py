# sandbox/api/websocket_extension.py
import logging
import asyncio
from typing import Dict, Any, Optional, Tuple, Union
import time

from ..core.synthetic_position_manager import SyntheticPositionManager
from ..core.risk_engine import RiskEngine
from ..hedging.hedging_engine import HedgingEngine
from ..config.sandbox_config import SANDBOX_CONFIG
from backend.trade_executor import TradeOrder, OrderSide
from backend.data_feed_manager import DataFeedManager
from backend.data_hub import DataHub

logger = logging.getLogger(__name__)

class SandboxService:
    """
    The sandbox service now reads data non-invasively from the central DataHub.
    """
    def __init__(self, data_hub: Union[DataFeedManager, DataHub], pricing_engine: Any, trade_executor: Any = None):
        self.data_hub = data_hub
        self.pricing_engine = pricing_engine
        self.trade_executor = trade_executor
        self.position_manager = SyntheticPositionManager(filepath='sandbox/config/synthetic_accounts.json')
        self.risk_engine = RiskEngine(self.position_manager)
        self.hedging_engine = HedgingEngine(self.pricing_engine)
        self.is_running = False
        logger.info("SandboxService initialized and configured to read from Data Hub.")

    async def _background_tasks_loop(self):
        """The internal processing loop for continuous analysis."""
        logger.info("Sandbox background tasks loop started.")
        while self.is_running:
            try:
                # Get the latest price using the appropriate method based on the instance type
                if isinstance(self.data_hub, DataFeedManager):
                    mark_price = self.data_hub.get_current_price()
                else:  # DataHub instance
                    mark_price = self.data_hub.get_current_price_sync()
                
                if mark_price and mark_price > 0:
                    perp_price = mark_price * 1.0001
                    self.position_manager.update_pnl_and_funding(mark_price, perp_price)
                    
                    # Sync positions with main trade executor if available
                    if self.trade_executor:
                        for account_id, account in self.position_manager.accounts.items():
                            if account_id in self.trade_executor.user_accounts:
                                self.trade_executor.user_accounts[account_id].active_positions = account.positions

                await asyncio.sleep(SANDBOX_CONFIG.HEDGING_CHECK_INTERVAL_SECONDS)
            except asyncio.CancelledError:
                logger.info("Sandbox background tasks loop cancelled.")
                break
            except Exception as e:
                logger.error(f"Error in sandbox background loop: {e}", exc_info=True)
                # Ensure we always sleep to prevent tight loop
                await asyncio.sleep(SANDBOX_CONFIG.HEDGING_CHECK_INTERVAL_SECONDS)

    def start(self):
        if not self.is_running:
            self.is_running = True
            try:
                loop = asyncio.get_running_loop()
                asyncio.create_task(self._background_tasks_loop())
            except RuntimeError:
                # No running event loop (e.g., during tests), skip background task
                logger.info("No running event loop; skipping background tasks loop (test mode)")

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

            # Create trade order for main executor if available
            if self.trade_executor:
                try:
                    # Create user account if it doesn't exist
                    if trade_data["user_id"] not in self.trade_executor.user_accounts:
                        self.trade_executor.create_user_account(trade_data["user_id"])

                    # Get option chain and matching quote
                    option_chain = self.pricing_engine.generate_option_chain(trade_data["expiry_minutes"])
                    if not option_chain:
                        return False, f"No option chain for expiry {trade_data['expiry_minutes']}", None
                    quotes_list = option_chain.calls if trade_data["option_type"] == "call" else option_chain.puts
                    matching_quote = next((q for q in quotes_list if abs(q.strike - trade_data["strike"]) < 1e-6), None)
                    if not matching_quote:
                        return False, f"Strike {trade_data['strike']} not found in option chain", None

                    # Construct TradeOrder
                    order = TradeOrder(
                        order_id=f"sandbox_{int(time.time()*1000)}_{trade_data['user_id'][-4:] if len(trade_data['user_id'])>=4 else trade_data['user_id']}",
                        user_id=trade_data["user_id"],
                        symbol=matching_quote.symbol,
                        side=OrderSide(trade_data["side"]),
                        quantity=trade_data["quantity"],
                        premium_per_contract=matching_quote.premium_usd,
                        total_premium=matching_quote.premium_usd * trade_data["quantity"],
                        option_type=trade_data["option_type"],
                        strike=trade_data["strike"],
                        expiry_minutes=trade_data["expiry_minutes"],
                        timestamp=time.time(),
                        greeks=matching_quote.greeks
                    )

                    # Execute trade in main system
                    success, message, position = self.trade_executor.execute_trade(order)
                    if not success:
                        return False, message, None
                except Exception as e:
                    logger.error(f"Error executing trade in main system: {e}", exc_info=True)
                    # Continue with sandbox execution as fallback

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
