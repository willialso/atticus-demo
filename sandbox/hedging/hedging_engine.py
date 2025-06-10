# sandbox/hedging/hedging_engine.py
import logging
from typing import Dict, Any
from .strategy_factory import StrategyFactory

logger = logging.getLogger(__name__)

class HedgingEngine:
    def __init__(self, pricing_engine: Any = None):
        """
        FIXED: Now accepts pricing_engine parameter to integrate with demo's live pricing.
        This supports your work on simulation trading and options trading strategies.
        """
        self.pricing_engine = pricing_engine
        self.strategy_factory = StrategyFactory(pricing_engine) if pricing_engine else StrategyFactory()
        logger.info("HedgingEngine initialized with live pricing integration.")

    def devise_hedging_plan(self, market_data: Dict, portfolio_summary: Dict):
        """Analyzes the portfolio and recommends hedging strategies based on live market data."""
        logger.info("Devising hedging plan using live demo pricing...")
        
        # Get strategy recommendations from the factory
        recommended_strategies = self.strategy_factory.run_all_strategies(market_data, portfolio_summary)
        
        if not recommended_strategies:
            logger.info("No hedging strategies recommended at this time.")
            return None
        
        # Return the top-ranked strategy
        top_hedge = recommended_strategies[0]
        logger.info(f"Top recommendation ({top_hedge.confidence_score:.2f}): {top_hedge.strategy_name}")
        logger.info(f"Reasoning: {top_hedge.reasoning}")
        
        return top_hedge
