import math
import numpy as np
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from ..strategy_factory import BaseStrategy, StrategyResult

logger = logging.getLogger(__name__)

class VolatilityStrategies(BaseStrategy):
    """Advanced volatility-based hedging and arbitrage strategies"""
    
    def __init__(self):
        super().__init__()
        self.name = "VolatilityStrategies"
    
    def volatility_arbitrage_strategy(self, current_price: float, implied_vol: float, 
                                    realized_vol: float, position_size: float = 1.0,
                                    time_horizon_hours: float = 8) -> StrategyResult:
        """
        Strategy 14: Volatility Skew Exploitation from document
        Advanced volatility arbitrage exploiting IV vs RV discrepancies
        """
        
        vol_spread = implied_vol - realized_vol
        vol_spread_pct = vol_spread / realized_vol if realized_vol > 0 else 0
        
        # Determine strategy direction based on vol spread
        if abs(vol_spread_pct) < 0.1:  # Less than 10% difference
            return StrategyResult(
                "volatility_arbitrage_strategy", 0.3, 0, 0, 0, [], 
                "Insufficient volatility spread for arbitrage"
            )
        
        # Strategy selection based on volatility relationship
        if vol_spread > 0.05:  # IV significantly higher than RV
            strategy_type = "sell_vol"
            confidence_base = 0.7
        elif vol_spread < -0.05:  # RV significantly higher than IV
            strategy_type = "buy_vol"
            confidence_base = 0.8
        else:
            strategy_type = "neutral"
            confidence_base = 0.5
        
        # Dynamic strike selection based on volatility skew
        if strategy_type == "sell_vol":
            # Sell overpriced options - prefer OTM options with high IV
            call_strike = current_price * 1.05  # 5% OTM call
            put_strike = current_price * 0.95   # 5% OTM put
            
            call_params = self._price_option_with_greeks(
                spot=current_price,
                strike=call_strike,
                time_to_expiry=time_horizon_hours / 24 / 365,
                volatility=implied_vol,
                option_type='call'
            )
            
            put_params = self._price_option_with_greeks(
                spot=current_price,
                strike=put_strike,
                time_to_expiry=time_horizon_hours / 24 / 365,
                volatility=implied_vol,
                option_type='put'
            )
            
            # Strangle sale strategy
            options_needed = [
                {
                    'type': 'call',
                    'strike': call_strike,
                    'expiry_hours': time_horizon_hours,
                    'quantity': position_size,
                    'action': 'sell',
                    'estimated_premium': call_params['premium'],
                    'greeks': call_params['greeks']
                },
                {
                    'type': 'put',
                    'strike': put_strike,
                    'expiry_hours': time_horizon_hours,
                    'quantity': position_size,
                    'action': 'sell',
                    'estimated_premium': put_params['premium'],
                    'greeks': put_params['greeks']
                }
            ]
            
            expected_return = (call_params['premium'] + put_params['premium']) * position_size
            max_loss = max(call_strike - current_price, current_price - put_strike) * position_size
            
        elif strategy_type == "buy_vol":
            # Buy underpriced options - ATM straddle for maximum gamma
            strike = current_price
            
            call_params = self._price_option_with_greeks(
                spot=current_price,
                strike=strike,
                time_to_expiry=time_horizon_hours / 24 / 365,
                volatility=implied_vol,
                option_type='call'
            )
            
            put_params = self._price_option_with_greeks(
                spot=current_price,
                strike=strike,
                time_to_expiry=time_horizon_hours / 24 / 365,
                volatility=implied_vol,
                option_type='put'
            )
            
            options_needed = [
                {
                    'type': 'call',
                    'strike': strike,
                    'expiry_hours': time_horizon_hours,
                    'quantity': position_size,
                    'action': 'buy',
                    'estimated_premium': call_params['premium'],
                    'greeks': call_params['greeks']
                },
                {
                    'type': 'put',
                    'strike': strike,
                    'expiry_hours': time_horizon_hours,
                    'quantity': position_size,
                    'action': 'buy',
                    'estimated_premium': put_params['premium'],
                    'greeks': put_params['greeks']
                }
            ]
            
            expected_cost = (call_params['premium'] + put_params['premium']) * position_size
            # Expected return based on realized vol being higher
            vol_move_expected = realized_vol - implied_vol
            expected_return = expected_cost * (vol_move_expected / implied_vol) * 2  # Simplified calculation
            max_loss = expected_cost
        
        # Confidence scoring
        vol_spread_confidence = min(1.0, abs(vol_spread_pct) / 0.3)  # Scale to 30% max spread
        time_horizon_factor = min(1.0, time_horizon_hours / 12)  # Prefer shorter horizons
        
        confidence_score = (
            confidence_base * 0.6 +
            vol_spread_confidence * 0.3 +
            time_horizon_factor * 0.1
        )
        
        return StrategyResult(
            strategy_name="volatility_arbitrage_strategy",
            confidence_score=confidence_score,
            expected_cost=expected_cost if strategy_type == "buy_vol" else -expected_return,
            expected_return=expected_return if strategy_type == "buy_vol" else expected_return,
            max_loss=max_loss,
            options_needed=options_needed,
            reasoning=f"Volatility arbitrage: {strategy_type}. IV: {implied_vol:.2f}, "
                     f"RV: {realized_vol:.2f}, Spread: {vol_spread_pct:.1%}",
            risk_metrics={
                'volatility_spread': vol_spread,
                'volatility_spread_pct': vol_spread_pct,
                'strategy_type': strategy_type,
                'implied_vol': implied_vol,
                'realized_vol': realized_vol
            }
        )
    
    def vega_hedging_strategy(self, portfolio_vega: float, current_price: float, 
                             volatility: float, target_vega: float = 0) -> StrategyResult:
        """
        Advanced vega hedging to neutralize volatility risk
        """
        
        vega_exposure = portfolio_vega - target_vega
        
        if abs(vega_exposure) < 5:  # Minimal vega exposure
            return StrategyResult(
                "vega_hedging_strategy", 0.3, 0, 0, 0, [], 
                "Portfolio vega within acceptable range"
            )
        
        # Determine hedge direction
        if vega_exposure > 0:  # Need to reduce positive vega (sell options)
            hedge_action = "sell"
            hedge_size = abs(vega_exposure)
        else:  # Need to increase vega (buy options)
            hedge_action = "buy"
            hedge_size = abs(vega_exposure)
        
        # Select optimal option for vega hedge
        # ATM options have highest vega per dollar
        strike = current_price
        expiry_hours = 8  # Medium-term for stable vega
        
        # Test both calls and puts to find best vega efficiency
        call_params = self._price_option_with_greeks(
            spot=current_price,
            strike=strike,
            time_to_expiry=expiry_hours / 24 / 365,
            volatility=volatility,
            option_type='call'
        )
        
        put_params = self._price_option_with_greeks(
            spot=current_price,
            strike=strike,
            time_to_expiry=expiry_hours / 24 / 365,
            volatility=volatility,
            option_type='put'
        )
        
        call_vega_efficiency = call_params['greeks']['vega'] / call_params['premium']
        put_vega_efficiency = put_params['greeks']['vega'] / put_params['premium']
        
        # Select more efficient option
        if call_vega_efficiency > put_vega_efficiency:
            selected_option = 'call'
            selected_params = call_params
            vega_per_contract = call_params['greeks']['vega']
        else:
            selected_option = 'put'
            selected_params = put_params
            vega_per_contract = put_params['greeks']['vega']
        
        # Calculate required contracts
        contracts_needed = hedge_size / abs(vega_per_contract)
        total_cost = selected_params['premium'] * contracts_needed
        
        if hedge_action == "sell":
            total_cost = -total_cost  # Receive premium
        
        options_needed = [{
            'type': selected_option,
            'strike': strike,
            'expiry_hours': expiry_hours,
            'quantity': contracts_needed,
            'action': hedge_action,
            'estimated_premium': selected_params['premium'],
            'greeks': selected_params['greeks']
        }]
        
        # Calculate hedge effectiveness
        hedge_effectiveness = min(1.0, abs(vega_per_contract * contracts_needed) / abs(vega_exposure))
        
        confidence_score = (
            hedge_effectiveness * 0.4 +
            min(1.0, abs(vega_exposure) / 50) * 0.3 +  # Higher confidence for larger exposures
            (call_vega_efficiency + put_vega_efficiency) / 2 * 0.3  # Efficiency factor
        )
        
        return StrategyResult(
            strategy_name="vega_hedging_strategy",
            confidence_score=confidence_score,
            expected_cost=total_cost,
            expected_return=0,  # Hedging strategy, not profit-seeking
            max_loss=abs(total_cost) if hedge_action == "buy" else total_cost * 2,
            options_needed=options_needed,
            reasoning=f"Vega hedge: {hedge_action} {contracts_needed:.2f} {selected_option}s. "
                     f"Portfolio vega: {portfolio_vega:.1f}, Target: {target_vega:.1f}",
            risk_metrics={
                'portfolio_vega': portfolio_vega,
                'vega_exposure': vega_exposure,
                'hedge_effectiveness': hedge_effectiveness,
                'contracts_needed': contracts_needed,
                'vega_per_contract': vega_per_contract
            }
        )
    
    def volatility_term_structure_arbitrage(self, current_price: float, 
                                           short_term_vol: float, long_term_vol: float,
                                           position_size: float = 1.0) -> StrategyResult:
        """
        Exploit volatility term structure anomalies
        Strategy 14 variant: Term structure arbitrage
        """
        
        vol_term_spread = short_term_vol - long_term_vol
        normal_term_spread = 0.05  # Normal backwardation expectation
        
        anomaly_size = vol_term_spread - normal_term_spread
        
        if abs(anomaly_size) < 0.03:  # Less than 3% anomaly
            return StrategyResult(
                "volatility_term_structure_arbitrage", 0.3, 0, 0, 0, [], 
                "Insufficient term structure anomaly"
            )
        
        short_expiry = 4  # hours
        long_expiry = 12  # hours
        
        if anomaly_size > 0:  # Short-term vol too high relative to long-term
            # Sell short-term, buy long-term
            strategy_direction = "sell_short_buy_long"
            
            # Short-term option (sell)
            short_strike = current_price
            short_params = self._price_option_with_greeks(
                spot=current_price,
                strike=short_strike,
                time_to_expiry=short_expiry / 24 / 365,
                volatility=short_term_vol,
                option_type='call'
            )
            
            # Long-term option (buy)
            long_strike = current_price
            long_params = self._price_option_with_greeks(
                spot=current_price,
                strike=long_strike,
                time_to_expiry=long_expiry / 24 / 365,
                volatility=long_term_vol,
                option_type='call'
            )
            
            options_needed = [
                {
                    'type': 'call',
                    'strike': short_strike,
                    'expiry_hours': short_expiry,
                    'quantity': position_size,
                    'action': 'sell',
                    'estimated_premium': short_params['premium'],
                    'greeks': short_params['greeks']
                },
                {
                    'type': 'call',
                    'strike': long_strike,
                    'expiry_hours': long_expiry,
                    'quantity': position_size,
                    'action': 'buy',
                    'estimated_premium': long_params['premium'],
                    'greeks': long_params['greeks']
                }
            ]
            
            net_cost = (long_params['premium'] - short_params['premium']) * position_size
            
        else:  # Long-term vol too high relative to short-term
            # Buy short-term, sell long-term
            strategy_direction = "buy_short_sell_long"
            
            short_strike = current_price
            short_params = self._price_option_with_greeks(
                spot=current_price,
                strike=short_strike,
                time_to_expiry=short_expiry / 24 / 365,
                volatility=short_term_vol,
                option_type='call'
            )
            
            long_strike = current_price
            long_params = self._price_option_with_greeks(
                spot=current_price,
                strike=long_strike,
                time_to_expiry=long_expiry / 24 / 365,
                volatility=long_term_vol,
                option_type='call'
            )
            
            options_needed = [
                {
                    'type': 'call',
                    'strike': short_strike,
                    'expiry_hours': short_expiry,
                    'quantity': position_size,
                    'action': 'buy',
                    'estimated_premium': short_params['premium'],
                    'greeks': short_params['greeks']
                },
                {
                    'type': 'call',
                    'strike': long_strike,
                    'expiry_hours': long_expiry,
                    'quantity': position_size,
                    'action': 'sell',
                    'estimated_premium': long_params['premium'],
                    'greeks': long_params['greeks']
                }
            ]
            
            net_cost = (short_params['premium'] - long_params['premium']) * position_size
        
        # Expected return based on term structure normalization
        expected_return = abs(anomaly_size) * current_price * position_size * 0.1  # Conservative estimate
        
        confidence_score = min(0.9, abs(anomaly_size) / 0.1 * 0.7 + 0.2)
        
        return StrategyResult(
            strategy_name="volatility_term_structure_arbitrage",
            confidence_score=confidence_score,
            expected_cost=max(0, net_cost),
            expected_return=expected_return,
            max_loss=abs(net_cost) + expected_return * 0.5,
            options_needed=options_needed,
            reasoning=f"Term structure arbitrage: {strategy_direction}. "
                     f"Short vol: {short_term_vol:.2f}, Long vol: {long_term_vol:.2f}, "
                     f"Anomaly: {anomaly_size:.3f}",
            risk_metrics={
                'short_term_vol': short_term_vol,
                'long_term_vol': long_term_vol,
                'vol_term_spread': vol_term_spread,
                'anomaly_size': anomaly_size,
                'strategy_direction': strategy_direction
            }
        )
