# sandbox/hedging/strategy_factory.py
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class StrategyResult:
    """Standardized result from a strategy analysis."""
    strategy_name: str
    confidence_score: float
    options_needed: List[Dict]
    reasoning: str

class BaseStrategy(ABC):
    """Abstract base class for all hedging strategies."""
    def __init__(self, pricing_engine: Any = None):
        """Initialize strategy with optional pricing engine for live calculations."""
        self.name = self.__class__.__name__
        self.pricing_engine = pricing_engine

    @abstractmethod
    def analyze(self, market_data: Dict, portfolio_summary: Dict) -> Optional[StrategyResult]:
        """The core analysis method that each concrete strategy must implement."""
        pass

    def _get_option_price(self, spot: float, strike: float, expiry_hours: float, vol: float, option_type: str) -> float:
        """Calculate option price using the live pricing engine if available."""
        if self.pricing_engine:
            time_to_expiry_years = expiry_hours / (24 * 365)
            try:
                # Use the demo's actual pricing logic
                return self.pricing_engine.calculate_option_price(spot, strike, time_to_expiry_years, vol, option_type)
            except Exception as e:
                logger.warning(f"Error using live pricer, falling back to simple calculation: {e}")
        
        # Fallback to simple Black-Scholes if no pricing engine
        from ..utils.black_scholes import simple_black_scholes
        return simple_black_scholes(spot, strike, expiry_hours/8760, vol, option_type)

class StrategyFactory:
    """Factory to create and manage different hedging strategy objects."""
    def __init__(self, pricing_engine: Any = None):
        """Initialize factory with optional pricing engine."""
        self._strategies = {}
        self.pricing_engine = pricing_engine
        logger.info("StrategyFactory initialized for live hedging analysis.")

    def register_strategy(self, name: str, strategy_class: type):
        """Register a strategy class with the factory."""
        self._strategies[name] = strategy_class

    def run_all_strategies(self, market_data, portfolio_summary) -> List[StrategyResult]:
        """Run all registered strategies and return sorted recommendations."""
        from .algorithms.protective_strategies import ProtectivePutStrategy, ProtectiveCallStrategy
        
        # Register available strategies
        self.register_strategy("protective_put", ProtectivePutStrategy)
        self.register_strategy("protective_call", ProtectiveCallStrategy)
        
        results = []
        for name, strategy_class in self._strategies.items():
            try:
                # Pass the pricing engine to each strategy instance
                strategy_instance = strategy_class(self.pricing_engine)
                result = strategy_instance.analyze(market_data, portfolio_summary)
                if result:
                    results.append(result)
                    logger.debug(f"Strategy '{name}' generated recommendation: {result.strategy_name}")
            except Exception as e:
                logger.error(f"Error analyzing with strategy '{name}': {e}")
        
        # Sort by confidence score (highest first)
        results.sort(key=lambda x: x.confidence_score, reverse=True)
        return results
