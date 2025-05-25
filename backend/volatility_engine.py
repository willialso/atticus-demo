# backend/volatility_engine.py
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from backend import config
from backend.utils import setup_logger
import math

logger = setup_logger(__name__)

@dataclass
class VolatilityMetrics:
    current_vol: float
    regime_vol: float
    ewma_vol: float
    garch_vol: Optional[float]
    confidence: float
    regime: str  # "low", "medium", "high"

class AdvancedVolatilityEngine:
    def __init__(self):
        self.price_history: List[float] = []
        self.return_history: List[float] = []
        self.regime_history: List[str] = []
        self.last_regime = "medium"
        
    def update_price(self, price: float) -> None:
        """Update with new price and calculate returns."""
        if price <= 0:
            return
            
        self.price_history.append(price)
        
        # Calculate log return if we have previous price
        if len(self.price_history) >= 2:
            log_return = math.log(price / self.price_history[-2])
            self.return_history.append(log_return)
            
        # Limit history size
        max_points = config.PRICE_HISTORY_MAX_POINTS
        if len(self.price_history) > max_points:
            self.price_history = self.price_history[-max_points:]
        if len(self.return_history) > max_points:
            self.return_history = self.return_history[-max_points:]
            
    def calculate_simple_historical_vol(self, periods: int = None) -> float:
        """Calculate simple historical volatility."""
        if len(self.return_history) < 20:
            return config.DEFAULT_VOLATILITY
            
        if periods is None:
            periods = min(len(self.return_history), 100)
            
        returns = np.array(self.return_history[-periods:])
        
        # Annualize based on data frequency
        sampling_freq = config.DATA_BROADCAST_INTERVAL_SECONDS
        periods_per_year = (365 * 24 * 60 * 60) / sampling_freq
        annualization_factor = math.sqrt(periods_per_year)
        
        vol = np.std(returns) * annualization_factor
        return max(vol, config.MIN_VOLATILITY)
    
    def calculate_ewma_volatility(self, alpha: float = None) -> float:
        """Calculate Exponentially Weighted Moving Average volatility."""
        if alpha is None:
            alpha = config.VOLATILITY_EWMA_ALPHA
            
        if len(self.return_history) < 10:
            return self.calculate_simple_historical_vol()
            
        returns = np.array(self.return_history)
        
        # EWMA calculation
        weights = [(1 - alpha) ** i for i in range(len(returns))]
        weights.reverse()
        weights = np.array(weights)
        weights /= weights.sum()
        
        # Weighted variance
        mean_return = np.average(returns, weights=weights)
        weighted_variance = np.average((returns - mean_return) ** 2, weights=weights)
        
        # Annualize
        sampling_freq = config.DATA_BROADCAST_INTERVAL_SECONDS
        periods_per_year = (365 * 24 * 60 * 60) / sampling_freq
        annualized_vol = math.sqrt(weighted_variance * periods_per_year)
        
        return max(annualized_vol, config.MIN_VOLATILITY)
    
    def detect_volatility_regime(self) -> str:
        """Detect current volatility regime using recent vol vs long-term vol."""
        if len(self.return_history) < 50:
            return "medium"
            
        short_vol = self.calculate_simple_historical_vol(20)
        long_vol = self.calculate_simple_historical_vol(100)
        
        ratio = short_vol / long_vol
        
        if ratio > 1.3:
            regime = "high"
        elif ratio < 0.7:
            regime = "low"  
        else:
            regime = "medium"
            
        self.last_regime = regime
        self.regime_history.append(regime)
        
        if len(self.regime_history) > 100:
            self.regime_history = self.regime_history[-100:]
            
        return regime
    
    def get_expiry_adjusted_volatility(self, expiry_minutes: int) -> float:
        """Adjust volatility based on expiry time frame."""
        base_vol = self.calculate_ewma_volatility()
        regime = self.detect_volatility_regime()
        
        # Regime adjustments
        regime_multipliers = {
            "low": 0.8,
            "medium": 1.0, 
            "high": 1.3
        }
        
        adjusted_vol = base_vol * regime_multipliers.get(regime, 1.0)
        
        # Time-based adjustments for very short expiries
        if expiry_minutes <= 15:
            # Very short-term options often have higher implied vol
            adjusted_vol *= 1.2
        elif expiry_minutes <= 60:
            adjusted_vol *= 1.1
            
        return max(min(adjusted_vol, config.MAX_VOLATILITY), config.MIN_VOLATILITY)
    
    def get_volatility_metrics(self) -> VolatilityMetrics:
        """Get comprehensive volatility metrics."""
        current_vol = self.calculate_simple_historical_vol()
        regime_vol = self.get_expiry_adjusted_volatility(60)  # 1hr baseline
        ewma_vol = self.calculate_ewma_volatility()
        regime = self.detect_volatility_regime()
        
        # Confidence based on data sufficiency
        confidence = min(len(self.return_history) / 100, 1.0)
        
        return VolatilityMetrics(
            current_vol=current_vol,
            regime_vol=regime_vol,
            ewma_vol=ewma_vol,
            garch_vol=None,  # Future enhancement
            confidence=confidence,
            regime=regime
        )
