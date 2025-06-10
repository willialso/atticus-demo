import math
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from ..strategy_factory import BaseStrategy, StrategyResult

logger = logging.getLogger(__name__)

class IncomeStrategies(BaseStrategy):
    """Income generation strategies for covered calls, covered puts, and theta farming"""
    
    def __init__(self):
        super().__init__()
        self.name = "IncomeStrategies"
    
    def covered_call_optimization(self, position_size: float, current_price: float, 
                                 entry_price: float, volatility: float,
                                 target_income_rate: float = 0.02) -> StrategyResult:
        """
        Strategy 4: Covered Call for Income on Long Perp
        Dynamic covered call with optimal strike selection for income
        """
        
        if position_size <= 0:
            return StrategyResult("covered_call_optimization", 0, 0, 0, 0, [], "No long position for covered calls")
        
        # Market condition assessment
        position_value = position_size * current_price
        unrealized_pnl = position_size * (current_price - entry_price)
        pnl_ratio = unrealized_pnl / position_value
        
        # Dynamic expiry selection based on volatility and income targets
        if volatility > 1.0:  # High vol = shorter expiry for premium capture
            expiry_hours = 4
            vol_multiplier = 1.2
        elif volatility > 0.7:
            expiry_hours = 8
            vol_multiplier = 1.0
        else:  # Low vol = longer expiry for time decay
            expiry_hours = 12
            vol_multiplier = 0.8
        
        # Strike selection algorithm
        strikes_to_test = []
        for moneyness in [0.02, 0.03, 0.04, 0.05, 0.06]:  # 2% to 6% OTM
            strikes_to_test.append(current_price * (1 + moneyness))
        
        best_strategy = None
        best_score = 0
        
        for strike in strikes_to_test:
            # Price the call option
            option_params = self._price_option_with_greeks(
                spot=current_price,
                strike=strike,
                time_to_expiry=expiry_hours / 24 / 365,
                volatility=volatility,
                option_type='call'
            )
            
            premium = option_params['premium']
            greeks = option_params['greeks']
            
            # Calculate income metrics
            premium_income = premium * position_size
            income_rate = premium_income / position_value
            assignment_probability = self._calculate_assignment_probability(current_price, strike, volatility, expiry_hours)
            
            # Risk-adjusted income score
            upside_cap = strike - current_price
            upside_cap_pct = upside_cap / current_price
            
            # Score factors
            income_score = min(1.0, income_rate / target_income_rate)
            assignment_risk_score = 1 - assignment_probability
            upside_preservation_score = min(1.0, upside_cap_pct / 0.05)  # Target 5% upside room
            greeks_score = self._assess_income_greeks(greeks)
            
            overall_score = (
                income_score * 0.4 +
                assignment_risk_score * 0.3 +
                upside_preservation_score * 0.2 +
                greeks_score * 0.1
            )
            
            if overall_score > best_score:
                best_score = overall_score
                best_strategy = {
                    'strike': strike,
                    'premium': premium,
                    'income_rate': income_rate,
                    'assignment_prob': assignment_probability,
                    'upside_cap_pct': upside_cap_pct,
                    'greeks': greeks,
                    'expiry_hours': expiry_hours
                }
        
        if not best_strategy:
            return StrategyResult("covered_call_optimization", 0, 0, 0, 0, [], "No viable covered call found")
        
        total_income = best_strategy['premium'] * position_size
        max_profit = total_income + max(0, best_strategy['strike'] - entry_price) * position_size
        
        return StrategyResult(
            strategy_name="covered_call_optimization",
            confidence_score=best_score,
            expected_cost=-total_income,  # Negative because we receive premium
            expected_return=total_income,
            max_loss=0,  # Covered call doesn't add downside risk
            options_needed=[{
                'type': 'call',
                'strike': best_strategy['strike'],
                'expiry_hours': best_strategy['expiry_hours'],
                'quantity': position_size,
                'action': 'sell',
                'estimated_premium': best_strategy['premium'],
                'greeks': best_strategy['greeks']
            }],
            reasoning=f"Optimal covered call at ${best_strategy['strike']:.0f} strike. "
                     f"Income rate: {best_strategy['income_rate']:.2%}, "
                     f"Assignment probability: {best_strategy['assignment_prob']:.1%}",
            risk_metrics={
                'income_rate': best_strategy['income_rate'],
                'assignment_probability': best_strategy['assignment_prob'],
                'upside_cap_percentage': best_strategy['upside_cap_pct'],
                'max_profit': max_profit
            }
        )
    
    def covered_put_optimization(self, position_size: float, current_price: float, 
                                entry_price: float, volatility: float,
                                target_income_rate: float = 0.02) -> StrategyResult:
        """
        Strategy 3: Covered Put for Income on Short Perp
        Dynamic covered put with optimal strike selection
        """
        
        if position_size >= 0:
            return StrategyResult("covered_put_optimization", 0, 0, 0, 0, [], "No short position for covered puts")
        
        position_value = abs(position_size) * current_price
        unrealized_pnl = position_size * (current_price - entry_price)  # Negative position_size
        
        # Dynamic parameters
        if volatility > 1.0:
            expiry_hours = 4
        elif volatility > 0.7:
            expiry_hours = 8
        else:
            expiry_hours = 12
        
        # Strike selection for puts (OTM = below current price)
        strikes_to_test = []
        for moneyness in [-0.06, -0.05, -0.04, -0.03, -0.02]:  # 2% to 6% OTM
            strikes_to_test.append(current_price * (1 + moneyness))
        
        best_strategy = None
        best_score = 0
        
        for strike in strikes_to_test:
            option_params = self._price_option_with_greeks(
                spot=current_price,
                strike=strike,
                time_to_expiry=expiry_hours / 24 / 365,
                volatility=volatility,
                option_type='put'
            )
            
            premium = option_params['premium']
            greeks = option_params['greeks']
            
            premium_income = premium * abs(position_size)
            income_rate = premium_income / position_value
            assignment_probability = self._calculate_assignment_probability(current_price, strike, volatility, expiry_hours, option_type='put')
            
            # For puts, downside room before assignment
            downside_room = current_price - strike
            downside_room_pct = downside_room / current_price
            
            # Scoring
            income_score = min(1.0, income_rate / target_income_rate)
            assignment_risk_score = 1 - assignment_probability
            downside_preservation_score = min(1.0, downside_room_pct / 0.05)
            greeks_score = self._assess_income_greeks(greeks)
            
            overall_score = (
                income_score * 0.4 +
                assignment_risk_score * 0.3 +
                downside_preservation_score * 0.2 +
                greeks_score * 0.1
            )
            
            if overall_score > best_score:
                best_score = overall_score
                best_strategy = {
                    'strike': strike,
                    'premium': premium,
                    'income_rate': income_rate,
                    'assignment_prob': assignment_probability,
                    'downside_room_pct': downside_room_pct,
                    'greeks': greeks,
                    'expiry_hours': expiry_hours
                }
        
        if not best_strategy:
            return StrategyResult("covered_put_optimization", 0, 0, 0, 0, [], "No viable covered put found")
        
        total_income = best_strategy['premium'] * abs(position_size)
        
        return StrategyResult(
            strategy_name="covered_put_optimization",
            confidence_score=best_score,
            expected_cost=-total_income,
            expected_return=total_income,
            max_loss=0,
            options_needed=[{
                'type': 'put',
                'strike': best_strategy['strike'],
                'expiry_hours': best_strategy['expiry_hours'],
                'quantity': abs(position_size),
                'action': 'sell',
                'estimated_premium': best_strategy['premium'],
                'greeks': best_strategy['greeks']
            }],
            reasoning=f"Optimal covered put at ${best_strategy['strike']:.0f} strike. "
                     f"Income rate: {best_strategy['income_rate']:.2%}, "
                     f"Assignment probability: {best_strategy['assignment_prob']:.1%}",
            risk_metrics={
                'income_rate': best_strategy['income_rate'],
                'assignment_probability': best_strategy['assignment_prob'],
                'downside_room_percentage': best_strategy['downside_room_pct'],
                'total_income': total_income
            }
        )
    
    def theta_farming_strategy(self, portfolio_delta: float, current_price: float, 
                              volatility: float, available_capital: float) -> StrategyResult:
        """
        Strategy 15: Time Decay (Theta) Farming with Perp
        Systematic theta capture through option selling
        """
        
        # Optimal theta farming parameters
        target_delta_neutrality = 0.1  # Allow small delta exposure
        max_position_size = available_capital * 0.2 / current_price  # 20% of capital
        
        # Time to expiry optimization for theta
        if volatility > 1.0:
            expiry_hours = 2  # High vol = capture fast decay
            vol_factor = 1.3
        elif volatility > 0.7:
            expiry_hours = 4
            vol_factor = 1.0
        else:
            expiry_hours = 8  # Low vol = need more time for theta
            vol_factor = 0.8
        
        strategies = []
        
        # Strategy 1: Sell ATM straddle for maximum theta
        atm_strike = current_price
        
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
        
        straddle_theta = call_params['greeks']['theta'] + put_params['greeks']['theta']
        straddle_premium = call_params['premium'] + put_params['premium']
        straddle_size = min(max_position_size, available_capital * 0.1 / (straddle_premium * current_price))
        
        # Strategy 2: Iron condor for range-bound theta farming
        otm_call_strike = current_price * 1.04
        otm_put_strike = current_price * 0.96
        
        otm_call_params = self._price_option_with_greeks(
            spot=current_price,
            strike=otm_call_strike,
            time_to_expiry=expiry_hours / 24 / 365,
            volatility=volatility,
            option_type='call'
        )
        
        otm_put_params = self._price_option_with_greeks(
            spot=current_price,
            strike=otm_put_strike,
            time_to_expiry=expiry_hours / 24 / 365,
            volatility=volatility,
            option_type='put'
        )
        
        condor_theta = otm_call_params['greeks']['theta'] + otm_put_params['greeks']['theta']
        condor_premium = otm_call_params['premium'] + otm_put_params['premium']
        condor_size = min(max_position_size, available_capital * 0.15 / (condor_premium * current_price))
        
        # Select best strategy based on theta/risk ratio
        straddle_theta_ratio = abs(straddle_theta) / straddle_premium if straddle_premium > 0 else 0
        condor_theta_ratio = abs(condor_theta) / condor_premium if condor_premium > 0 else 0
        
        if straddle_theta_ratio > condor_theta_ratio and volatility < 0.8:  # Straddle better in low vol
            selected_strategy = "atm_straddle"
            total_theta = straddle_theta * straddle_size
            total_premium = straddle_premium * straddle_size
            position_size = straddle_size
            
            options_needed = [
                {
                    'type': 'call',
                    'strike': atm_strike,
                    'expiry_hours': expiry_hours,
                    'quantity': position_size,
                    'action': 'sell',
                    'estimated_premium': call_params['premium'],
                    'greeks': call_params['greeks']
                },
                {
                    'type': 'put',
                    'strike': atm_strike,
                    'expiry_hours': expiry_hours,
                    'quantity': position_size,
                    'action': 'sell',
                    'estimated_premium': put_params['premium'],
                    'greeks': put_params['greeks']
                }
            ]
            
        else:  # Iron condor for higher vol or better risk-adjusted theta
            selected_strategy = "iron_condor"
            total_theta = condor_theta * condor_size
            total_premium = condor_premium * condor_size
            position_size = condor_size
            
            options_needed = [
                {
                    'type': 'call',
                    'strike': otm_call_strike,
                    'expiry_hours': expiry_hours,
                    'quantity': position_size,
                    'action': 'sell',
                    'estimated_premium': otm_call_params['premium'],
                    'greeks': otm_call_params['greeks']
                },
                {
                    'type': 'put',
                    'strike': otm_put_strike,
                    'expiry_hours': expiry_hours,
                    'quantity': position_size,
                    'action': 'sell',
                    'estimated_premium': otm_put_params['premium'],
                    'greeks': otm_put_params['greeks']
                }
            ]
        
        # Confidence based on theta efficiency and market conditions
        theta_efficiency = abs(total_theta) / total_premium if total_premium > 0 else 0
        market_stability = 1 - min(1.0, volatility / 1.5)  # Lower vol = more stable = better for theta
        
        confidence_score = (
            min(1.0, theta_efficiency / 0.05) * 0.5 +  # Target 5% daily theta
            market_stability * 0.3 +
            min(1.0, position_size / (max_position_size * 0.5)) * 0.2  # Size utilization
        )
        
        daily_theta_income = abs(total_theta) * 24 / expiry_hours  # Annualized to daily
        
        return StrategyResult(
            strategy_name="theta_farming_strategy",
            confidence_score=confidence_score,
            expected_cost=-total_premium,  # We receive premium
            expected_return=daily_theta_income,
            max_loss=total_premium * 2,  # Estimate max loss as 2x premium received
            options_needed=options_needed,
            reasoning=f"Theta farming via {selected_strategy}. "
                     f"Daily theta income: ${daily_theta_income:.2f}, "
                     f"Theta efficiency: {theta_efficiency:.3f}",
            risk_metrics={
                'theta_efficiency': theta_efficiency,
                'daily_theta_income': daily_theta_income,
                'market_stability_score': market_stability,
                'strategy_type': selected_strategy
            }
        )
    
    def rolling_income_strategy(self, current_positions: List[Dict], current_price: float, 
                               volatility: float) -> StrategyResult:
        """
        Strategy 10: Rolling Options for Continuous Income with Perp
        Dynamic rolling of short options for continuous income
        """
        
        # Analyze current short option positions for rolling opportunities
        rollable_positions = []
        total_current_premium = 0
        
        for pos in current_positions:
            if pos.get('action') == 'sell' and pos.get('expiry_hours', 0) <= 2:
                # Position is near expiry and should be rolled
                current_premium = pos.get('estimated_premium', 0) * pos.get('quantity', 0)
                total_current_premium += current_premium
                
                # Calculate current option value
                current_value = self._price_option_with_greeks(
                    spot=current_price,
                    strike=pos['strike'],
                    time_to_expiry=max(0.01, pos.get('expiry_hours', 1) / 24 / 365),
                    volatility=volatility,
                    option_type=pos['type']
                )['premium']
                
                profit_so_far = current_premium - (current_value * pos.get('quantity', 0))
                
                rollable_positions.append({
                    'original_position': pos,
                    'current_value': current_value,
                    'profit_so_far': profit_so_far,
                    'should_roll': profit_so_far > current_premium * 0.5  # Roll if captured 50% profit
                })
        
        if not rollable_positions:
            return StrategyResult("rolling_income_strategy", 0, 0, 0, 0, [], "No positions ready for rolling")
        
        # Generate rolling strategy
        new_positions = []
        total_roll_cost = 0
        total_new_premium = 0
        
        for rollable in rollable_positions:
            if rollable['should_roll']:
                orig_pos = rollable['original_position']
                
                # Close current position (buy back)
                total_roll_cost += rollable['current_value'] * orig_pos.get('quantity', 0)
                
                # Open new position with same delta but further expiry
                new_expiry = 8  # Roll to 8-hour expiry
                
                # Adjust strike based on market movement and volatility
                if orig_pos['type'] == 'call':
                    # Roll call up and out if profitable
                    strike_adjustment = 0.01 if rollable['profit_so_far'] > 0 else 0
                    new_strike = current_price * (1 + 0.03 + strike_adjustment)
                else:  # put
                    # Roll put down and out if profitable
                    strike_adjustment = -0.01 if rollable['profit_so_far'] > 0 else 0
                    new_strike = current_price * (1 - 0.03 + strike_adjustment)
                
                new_option_params = self._price_option_with_greeks(
                    spot=current_price,
                    strike=new_strike,
                    time_to_expiry=new_expiry / 24 / 365,
                    volatility=volatility,
                    option_type=orig_pos['type']
                )
                
                new_premium = new_option_params['premium'] * orig_pos.get('quantity', 0)
                total_new_premium += new_premium
                
                new_positions.append({
                    'type': orig_pos['type'],
                    'strike': new_strike,
                    'expiry_hours': new_expiry,
                    'quantity': orig_pos.get('quantity', 0),
                    'action': 'sell',
                    'estimated_premium': new_option_params['premium'],
                    'greeks': new_option_params['greeks']
                })
        
        net_credit = total_new_premium - total_roll_cost
        roll_efficiency = net_credit / total_current_premium if total_current_premium > 0 else 0
        
        confidence_score = (
            min(1.0, max(0, roll_efficiency)) * 0.4 +  # Positive net credit is good
            len(new_positions) / max(1, len(rollable_positions)) * 0.3 +  # Rolling success rate
            min(1.0, volatility / 0.8) * 0.3  # Higher vol = better for option selling
        )
        
        return StrategyResult(
            strategy_name="rolling_income_strategy",
            confidence_score=confidence_score,
            expected_cost=-net_credit,  # Negative if we receive net credit
            expected_return=abs(net_credit) if net_credit > 0 else 0,
            max_loss=total_roll_cost,
            options_needed=new_positions,
            reasoning=f"Rolling {len(new_positions)} positions for continuous income. "
                     f"Net credit: ${net_credit:.2f}, Roll efficiency: {roll_efficiency:.2f}",
