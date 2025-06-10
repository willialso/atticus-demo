import math
import numpy as np
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from ..strategy_factory import BaseStrategy, StrategyResult

logger = logging.getLogger(__name__)

class DeltaNeutralStrategies(BaseStrategy):
    """Advanced delta neutral and gamma scalping strategies"""
    
    def __init__(self):
        super().__init__()
        self.name = "DeltaNeutralStrategies"
    
    def dynamic_delta_hedging(self, portfolio_delta: float, current_price: float, 
                             volatility: float, position_size: float,
                             hedge_tolerance: float = 0.05) -> StrategyResult:
        """
        Strategy 9: Delta Neutral Hedging from document
        Advanced dynamic delta hedging with real-time adjustments
        """
        
        target_delta = 0.0
        delta_deviation = abs(portfolio_delta - target_delta)
        
        # Check if hedging is needed
        if delta_deviation < hedge_tolerance:
            return StrategyResult(
                "dynamic_delta_hedging", 0.4, 0, 0, 0, [], 
                f"Portfolio delta {portfolio_delta:.3f} within tolerance {hedge_tolerance:.3f}"
            )
        
        # Calculate hedge requirements
        hedge_delta_needed = -portfolio_delta  # Opposite delta to neutralize
        
        # Strategy selection based on market conditions and efficiency
        hedge_options = []
        
        # Option 1: ATM straddle for neutral positioning
        if abs(hedge_delta_needed) > 0.3:  # Large delta exposure
            atm_strike = current_price
            expiry_hours = 6  # Medium-term for stability
            
            call_params = self._price_option_with_greeks(
                spot=current_price,
                strike=atm_strike,
                time_to_expiry=expiry_hours / 24 / 365,
                volatility=volatility,
                option_type='call'
            )
            
            put_params = self._price_option_with_greeks(
                spot=current_price,
                strike=atm_strike,
                time_to_expiry=expiry_hours / 24 / 365,
                volatility=volatility,
                option_type='put'
            )
            
            # Determine optimal combination
            if hedge_delta_needed > 0:  # Need positive delta
                # Buy calls or sell puts
                call_contracts = hedge_delta_needed / call_params['greeks']['delta']
                put_contracts = hedge_delta_needed / (-put_params['greeks']['delta'])
                
                call_cost = call_contracts * call_params['premium']
                put_income = put_contracts * put_params['premium']
                
                if call_cost < put_income:  # Buying calls is cheaper
                    selected_hedge = "buy_calls"
                    contracts_needed = call_contracts
                    cost = call_cost
                    hedge_option = {
                        'type': 'call',
                        'strike': atm_strike,
                        'expiry_hours': expiry_hours,
                        'quantity': contracts_needed,
                        'action': 'buy',
                        'estimated_premium': call_params['premium'],
                        'greeks': call_params['greeks']
                    }
                else:  # Selling puts is better
                    selected_hedge = "sell_puts"
                    contracts_needed = put_contracts
                    cost = -put_income  # Receive premium
                    hedge_option = {
                        'type': 'put',
                        'strike': atm_strike,
                        'expiry_hours': expiry_hours,
                        'quantity': contracts_needed,
                        'action': 'sell',
                        'estimated_premium': put_params['premium'],
                        'greeks': put_params['greeks']
                    }
            
            else:  # Need negative delta
                # Buy puts or sell calls
                put_contracts = abs(hedge_delta_needed) / put_params['greeks']['delta']
                call_contracts = abs(hedge_delta_needed) / call_params['greeks']['delta']
                
                put_cost = put_contracts * put_params['premium']
                call_income = call_contracts * call_params['premium']
                
                if put_cost < call_income:  # Buying puts is cheaper
                    selected_hedge = "buy_puts"
                    contracts_needed = put_contracts
                    cost = put_cost
                    hedge_option = {
                        'type': 'put',
                        'strike': atm_strike,
                        'expiry_hours': expiry_hours,
                        'quantity': contracts_needed,
                        'action': 'buy',
                        'estimated_premium': put_params['premium'],
                        'greeks': put_params['greeks']
                    }
                else:  # Selling calls is better
                    selected_hedge = "sell_calls"
                    contracts_needed = call_contracts
                    cost = -call_income  # Receive premium
                    hedge_option = {
                        'type': 'call',
                        'strike': atm_strike,
                        'expiry_hours': expiry_hours,
                        'quantity': contracts_needed,
                        'action': 'sell',
                        'estimated_premium': call_params['premium'],
                        'greeks': call_params['greeks']
                    }
            
            hedge_options.append(hedge_option)
        
        # Calculate hedge effectiveness
        hedged_delta = hedge_option['greeks']['delta'] * contracts_needed
        if hedge_option['action'] == 'sell':
            hedged_delta = -hedged_delta
        
        final_portfolio_delta = portfolio_delta + hedged_delta
        hedge_effectiveness = 1 - abs(final_portfolio_delta) / abs(portfolio_delta)
        
        # Confidence scoring
        effectiveness_score = hedge_effectiveness
        urgency_score = min(1.0, delta_deviation / 0.5)  # Scale to 50% max deviation
        cost_efficiency = 1 - min(1.0, abs(cost) / (position_size * current_price * 0.02))
        
        confidence_score = (
            effectiveness_score * 0.4 +
            urgency_score * 0.3 +
            cost_efficiency * 0.3
        )
        
        return StrategyResult(
            strategy_name="dynamic_delta_hedging",
            confidence_score=confidence_score,
            expected_cost=max(0, cost),
            expected_return=0,  # Hedging strategy
            max_loss=abs(cost) if cost > 0 else cost * 2,
            options_needed=hedge_options,
            reasoning=f"Delta hedge: {selected_hedge}. Portfolio delta: {portfolio_delta:.3f}, "
                     f"After hedge: {final_portfolio_delta:.3f}, Effectiveness: {hedge_effectiveness:.2%}",
            risk_metrics={
                'initial_portfolio_delta': portfolio_delta,
                'hedge_delta_needed': hedge_delta_needed,
                'final_portfolio_delta': final_portfolio_delta,
                'hedge_effectiveness': hedge_effectiveness,
                'selected_hedge': selected_hedge
            }
        )
    
    def gamma_scalping_strategy(self, portfolio_gamma: float, current_price: float, 
                               volatility: float, price_change_threshold: float = 0.01) -> StrategyResult:
        """
        Strategy 11: Gamma Scalping with Perp from document
        Advanced gamma scalping for volatility capture
        """
        
        if portfolio_gamma < 0.01:  # Insufficient gamma for scalping
            return StrategyResult(
                "gamma_scalping_strategy", 0.3, 0, 0, 0, [], 
                "Insufficient portfolio gamma for effective scalping"
            )
        
        # Optimal gamma scalping setup
        target_gamma = max(0.1, portfolio_gamma * 1.5)  # Increase gamma exposure
        gamma_deficit = target_gamma - portfolio_gamma
        
        # ATM straddle for maximum gamma
        strike = current_price
        expiry_hours = 4  # Short-term for maximum gamma sensitivity
        
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
        
        straddle_gamma = call_params['greeks']['gamma'] + put_params['greeks']['gamma']
        straddle_cost = call_params['premium'] + put_params['premium']
        
        # Calculate contracts needed for target gamma
        contracts_needed = gamma_deficit / straddle_gamma if straddle_gamma > 0 else 0
        total_cost = straddle_cost * contracts_needed
        
        # Gamma scalping profit estimation
        daily_vol = volatility / math.sqrt(365)
        expected_price_moves = 8  # Assume 8 moves per day
        avg_move_size = daily_vol * current_price / math.sqrt(expected_price_moves)
        
        # Gamma profit per move
        gamma_profit_per_move = 0.5 * (target_gamma * contracts_needed) * (avg_move_size ** 2)
        daily_gamma_profit = gamma_profit_per_move * expected_price_moves
        
        # Theta decay cost
        total_theta = (call_params['greeks']['theta'] + put_params['greeks']['theta']) * contracts_needed
        daily_theta_cost = abs(total_theta)  # Theta is already daily
        
        # Net expected return
        net_daily_return = daily_gamma_profit - daily_theta_cost
        scalping_efficiency = daily_gamma_profit / daily_theta_cost if daily_theta_cost > 0 else 0
        
        options_needed = [
            {
                'type': 'call',
                'strike': strike,
                'expiry_hours': expiry_hours,
                'quantity': contracts_needed,
                'action': 'buy',
                'estimated_premium': call_params['premium'],
                'greeks': call_params['greeks']
            },
            {
                'type': 'put',
                'strike': strike,
                'expiry_hours': expiry_hours,
                'quantity': contracts_needed,
                'action': 'buy',
                'estimated_premium': put_params['premium'],
                'greeks': put_params['greeks']
            }
        ]
        
        # Confidence based on scalping efficiency and market conditions
        efficiency_score = min(1.0, scalping_efficiency / 1.2)  # Target 1.2 gamma/theta ratio
        volatility_score = min(1.0, volatility / 1.0)  # Higher vol = better for scalping
        gamma_utilization = min(1.0, target_gamma / 0.2)  # Scale to 20% target gamma
        
        confidence_score = (
            efficiency_score * 0.4 +
            volatility_score * 0.3 +
            gamma_utilization * 0.3
        )
        
        return StrategyResult(
            strategy_name="gamma_scalping_strategy",
            confidence_score=confidence_score,
            expected_cost=total_cost,
            expected_return=max(0, net_daily_return),
            max_loss=total_cost,
            options_needed=options_needed,
            reasoning=f"Gamma scalping with {contracts_needed:.2f} ATM straddles. "
                     f"Target gamma: {target_gamma:.3f}, Efficiency: {scalping_efficiency:.2f}, "
                     f"Net daily return: ${net_daily_return:.2f}",
            risk_metrics={
                'portfolio_gamma': portfolio_gamma,
                'target_gamma': target_gamma,
                'contracts_needed': contracts_needed,
                'scalping_efficiency': scalping_efficiency,
                'daily_gamma_profit': daily_gamma_profit,
                'daily_theta_cost': daily_theta_cost,
                'net_daily_return': net_daily_return
            }
        )
    
    def delta_neutral_income_strategy(self, portfolio_delta: float, current_price: float, 
                                    volatility: float, income_target: float = 0.02) -> StrategyResult:
        """
        Delta neutral strategy focused on income generation through time decay
        """
        
        # Establish delta neutral position with income focus
        target_delta = 0.0
        
        # Iron condor strategy for delta neutral income
        otm_put_strike = current_price * 0.97  # 3% OTM put
        itm_put_strike = current_price * 0.94  # 6% OTM put (buy)
        otm_call_strike = current_price * 1.03  # 3% OTM call
        itm_call_strike = current_price * 1.06  # 6% OTM call (buy)
        
        expiry_hours = 8  # Daily income cycle
        
        # Price all options
        sell_put_params = self._price_option_with_greeks(
            spot=current_price, strike=otm_put_strike,
            time_to_expiry=expiry_hours / 24 / 365, volatility=volatility, option_type='put'
        )
        
        buy_put_params = self._price_option_with_greeks(
            spot=current_price, strike=itm_put_strike,
            time_to_expiry=expiry_hours / 24 / 365, volatility=volatility, option_type='put'
        )
        
        sell_call_params = self._price_option_with_greeks(
            spot=current_price, strike=otm_call_strike,
            time_to_expiry=expiry_hours / 24 / 365, volatility=volatility, option_type='call'
        )
        
        buy_call_params = self._price_option_with_greeks(
            spot=current_price, strike=itm_call_strike,
            time_to_expiry=expiry_hours / 24 / 365, volatility=volatility, option_type='call'
        )
        
        # Calculate iron condor metrics
        net_premium = (
            sell_put_params['premium'] + sell_call_params['premium'] -
            buy_put_params['premium'] - buy_call_params['premium']
        )
        
        net_delta = (
            -sell_put_params['greeks']['delta'] + buy_put_params['greeks']['delta'] +
            -sell_call_params['greeks']['delta'] + buy_call_params['greeks']['delta']
        )
        
        # Adjust for existing portfolio delta
        contracts_multiplier = 1.0
        if abs(portfolio_delta) > 0.1:
            # Adjust condor to offset portfolio delta
            delta_adjustment = -portfolio_delta / net_delta if net_delta != 0 else 1.0
            contracts_multiplier = abs(delta_adjustment)
        
        position_size = contracts_multiplier
        total_income = net_premium * position_size
        income_rate = total_income / current_price
        
        # Maximum risk calculation
        put_spread_width = otm_put_strike - itm_put_strike
        call_spread_width = itm_call_strike - otm_call_strike
        max_loss = min(put_spread_width, call_spread_width) * position_size - total_income
        
        options_needed = [
            {
                'type': 'put', 'strike': otm_put_strike, 'expiry_hours': expiry_hours,
                'quantity': position_size, 'action': 'sell',
                'estimated_premium': sell_put_params['premium'],
                'greeks': sell_put_params['greeks']
            },
            {
                'type': 'put', 'strike': itm_put_strike, 'expiry_hours': expiry_hours,
                'quantity': position_size, 'action': 'buy',
                'estimated_premium': buy_put_params['premium'],
                'greeks': buy_put_params['greeks']
            },
            {
                'type': 'call', 'strike': otm_call_strike, 'expiry_hours': expiry_hours,
                'quantity': position_size, 'action': 'sell',
                'estimated_premium': sell_call_params['premium'],
                'greeks': sell_call_params['greeks']
            },
            {
                'type': 'call', 'strike': itm_call_strike, 'expiry_hours': expiry_hours,
                'quantity': position_size, 'action': 'buy',
                'estimated_premium': buy_call_params['premium'],
                'greeks': buy_call_params['greeks']
            }
        ]
        
        # Success probability (price stays between short strikes)
        success_probability = 0.7  # Simplified - normally would use probability calculations
        
        # Confidence scoring
        income_efficiency = min(1.0, income_rate / income_target)
        delta_neutrality = max(0, 1 - abs(net_delta * position_size) / 0.1)
        risk_reward = min(1.0, total_income / max_loss) if max_loss > 0 else 0
        
        confidence_score = (
            income_efficiency * 0.35 +
            delta_neutrality * 0.25 +
            risk_reward * 0.25 +
            success_probability * 0.15
        )
        
        return StrategyResult(
            strategy_name="delta_neutral_income_strategy",
            confidence_score=confidence_score,
            expected_cost=-total_income,  # Receive premium
            expected_return=total_income * success_probability,
            max_loss=max_loss,
            options_needed=options_needed,
            reasoning=f"Delta neutral iron condor. Income: ${total_income:.2f} ({income_rate:.2%}), "
                     f"Max loss: ${max_loss:.2f}, Success prob: {success_probability:.0%}",
            risk_metrics={
                'net_premium': net_premium,
                'net_delta': net_delta * position_size,
                'income_rate': income_rate,
                'max_loss': max_loss,
                'success_probability': success_probability,
                'risk_reward_ratio': total_income / max_loss if max_loss > 0 else 0
            }
        )
