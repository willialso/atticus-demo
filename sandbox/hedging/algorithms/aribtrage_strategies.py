import math
import asyncio
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from ..strategy_factory import BaseStrategy, StrategyResult

logger = logging.getLogger(__name__)

class ArbitrageStrategies(BaseStrategy):
    """Advanced arbitrage strategies for cross-platform and cross-instrument opportunities"""
    
    def __init__(self):
        super().__init__()
        self.name = "ArbitrageStrategies"
        self.price_tolerance = 0.001  # 0.1% minimum for arbitrage
    
    def put_call_parity_arbitrage(self, call_price: float, put_price: float, 
                                 spot_price: float, strike_price: float,
                                 time_to_expiry: float, risk_free_rate: float = 0.05) -> StrategyResult:
        """
        Strategy 12: Arbitrage Between Perp and Options Markets from document
        Put-call parity arbitrage detection and execution
        """
        
        # Put-call parity: C - P = S - K*e^(-r*T)
        theoretical_parity = spot_price - strike_price * math.exp(-risk_free_rate * time_to_expiry)
        actual_parity = call_price - put_price
        parity_violation = actual_parity - theoretical_parity
        
        # Check if arbitrage opportunity exists
        if abs(parity_violation) < self.price_tolerance * spot_price:
            return StrategyResult(
                "put_call_parity_arbitrage", 0.2, 0, 0, 0, [], 
                f"No significant parity violation: {parity_violation:.4f}"
            )
        
        # Determine arbitrage strategy
        if parity_violation > 0:  # Call overpriced relative to put
            strategy_type = "sell_call_buy_put_buy_underlying"
            # Sell call, buy put, buy underlying asset
            
            options_needed = [
                {
                    'type': 'call',
                    'strike': strike_price,
                    'expiry_hours': time_to_expiry * 24 * 365,
                    'quantity': 1.0,
                    'action': 'sell',
                    'estimated_premium': call_price,
                    'greeks': {'delta': 0.5}  # Simplified
                },
                {
                    'type': 'put',
                    'strike': strike_price,
                    'expiry_hours': time_to_expiry * 24 * 365,
                    'quantity': 1.0,
                    'action': 'buy',
                    'estimated_premium': put_price,
                    'greeks': {'delta': -0.5}  # Simplified
                }
            ]
            
            # Calculate costs and returns
            option_net_flow = call_price - put_price  # Receive net premium
            underlying_cost = spot_price
            total_cost = underlying_cost - option_net_flow
            
            # At expiry, guaranteed profit is the parity violation
            guaranteed_profit = abs(parity_violation)
            
        else:  # Put overpriced relative to call
            strategy_type = "buy_call_sell_put_sell_underlying"
            # Buy call, sell put, sell underlying asset
            
            options_needed = [
                {
                    'type': 'call',
                    'strike': strike_price,
                    'expiry_hours': time_to_expiry * 24 * 365,
                    'quantity': 1.0,
                    'action': 'buy',
                    'estimated_premium': call_price,
                    'greeks': {'delta': 0.5}
                },
                {
                    'type': 'put',
                    'strike': strike_price,
                    'expiry_hours': time_to_expiry * 24 * 365,
                    'quantity': 1.0,
                    'action': 'sell',
                    'estimated_premium': put_price,
                    'greeks': {'delta': -0.5}
                }
            ]
            
            option_net_flow = put_price - call_price  # Receive net premium
            underlying_proceeds = spot_price
            total_proceeds = underlying_proceeds + option_net_flow
            
            guaranteed_profit = abs(parity_violation)
            total_cost = 0  # We receive money upfront
        
        # Risk assessment
        execution_risk = min(0.3, abs(parity_violation) / (spot_price * 0.01))  # Scale execution difficulty
        
        # Confidence scoring - arbitrage should be high confidence when violations are clear
        violation_significance = min(1.0, abs(parity_violation) / (spot_price * 0.005))  # Scale to 0.5%
        time_factor = max(0.3, 1 - time_to_expiry * 10)  # Prefer shorter expiries
        
        confidence_score = (
            violation_significance * 0.6 +
            time_factor * 0.3 +
            (1 - execution_risk) * 0.1
        )
        
        return StrategyResult(
            strategy_name="put_call_parity_arbitrage",
            confidence_score=confidence_score,
            expected_cost=max(0, total_cost) if parity_violation > 0 else 0,
            expected_return=guaranteed_profit,
            max_loss=0,  # True arbitrage has no loss if executed properly
            options_needed=options_needed,
            reasoning=f"Put-call parity arbitrage: {strategy_type}. "
                     f"Violation: ${parity_violation:.4f}, Guaranteed profit: ${guaranteed_profit:.4f}",
            risk_metrics={
                'parity_violation': parity_violation,
                'theoretical_parity': theoretical_parity,
                'actual_parity': actual_parity,
                'guaranteed_profit': guaranteed_profit,
                'strategy_type': strategy_type,
                'execution_risk': execution_risk
            }
        )
    
    def cross_exchange_arbitrage(self, exchange_prices: Dict[str, float], 
                                trading_fees: Dict[str, float] = None,
                                transfer_costs: Dict[str, float] = None) -> StrategyResult:
        """
        Cross-exchange arbitrage for Bitcoin price differences
        """
        
        if len(exchange_prices) < 2:
            return StrategyResult(
                "cross_exchange_arbitrage", 0.1, 0, 0, 0, [], 
                "Need at least 2 exchanges for arbitrage"
            )
        
        # Set default fees if not provided
        if trading_fees is None:
            trading_fees = {exchange: 0.001 for exchange in exchange_prices.keys()}  # 0.1% default
        if transfer_costs is None:
            transfer_costs = {exchange: 50 for exchange in exchange_prices.keys()}  # $50 default
        
        # Find best arbitrage opportunity
        exchanges = list(exchange_prices.keys())
        best_opportunity = None
        max_profit = 0
        
        for buy_exchange in exchanges:
            for sell_exchange in exchanges:
                if buy_exchange == sell_exchange:
                    continue
                
                buy_price = exchange_prices[buy_exchange]
                sell_price = exchange_prices[sell_exchange]
                
                # Calculate costs
                buy_fee = buy_price * trading_fees.get(buy_exchange, 0.001)
                sell_fee = sell_price * trading_fees.get(sell_exchange, 0.001)
                transfer_cost = transfer_costs.get(buy_exchange, 50)
                
                # Net profit per BTC
                gross_profit = sell_price - buy_price
                net_profit = gross_profit - buy_fee - sell_fee - transfer_cost
                profit_margin = net_profit / buy_price
                
                if net_profit > max_profit and profit_margin > self.price_tolerance:
                    max_profit = net_profit
                    best_opportunity = {
                        'buy_exchange': buy_exchange,
                        'sell_exchange': sell_exchange,
                        'buy_price': buy_price,
                        'sell_price': sell_price,
                        'gross_profit': gross_profit,
                        'net_profit': net_profit,
                        'profit_margin': profit_margin,
                        'total_costs': buy_fee + sell_fee + transfer_cost
                    }
        
        if not best_opportunity:
            return StrategyResult(
                "cross_exchange_arbitrage", 0.2, 0, 0, 0, [], 
                "No profitable arbitrage opportunities found"
            )
        
        # Calculate position sizing based on available capital and exchange limits
        max_position_size = 5.0  # Max 5 BTC for demo
        optimal_size = min(max_position_size, 1.0)  # Conservative sizing
        
        total_profit = best_opportunity['net_profit'] * optimal_size
        total_cost = best_opportunity['buy_price'] * optimal_size
        
        # Risk factors
        execution_speed_risk = 0.1  # 10% risk of price movement during execution
        transfer_time_risk = 0.05   # 5% risk from transfer delays
        
        # Confidence scoring
        profit_margin_score = min(1.0, best_opportunity['profit_margin'] / 0.01)  # Scale to 1%
        opportunity_size_score = min(1.0, total_profit / 100)  # Scale to $100 profit
        execution_certainty = 1 - execution_speed_risk - transfer_time_risk
        
        confidence_score = (
            profit_margin_score * 0.4 +
            opportunity_size_score * 0.3 +
            execution_certainty * 0.3
        )
        
        return StrategyResult(
            strategy_name="cross_exchange_arbitrage",
            confidence_score=confidence_score,
            expected_cost=total_cost,
            expected_return=total_profit,
            max_loss=total_cost * 0.02,  # Assume max 2% adverse movement
            options_needed=[],  # No options involved
            reasoning=f"Cross-exchange arbitrage: Buy {optimal_size} BTC on {best_opportunity['buy_exchange']} "
                     f"at ${best_opportunity['buy_price']:.2f}, sell on {best_opportunity['sell_exchange']} "
                     f"at ${best_opportunity['sell_price']:.2f}. Net profit: ${total_profit:.2f}",
            risk_metrics={
                'buy_exchange': best_opportunity['buy_exchange'],
                'sell_exchange': best_opportunity['sell_exchange'],
                'profit_margin': best_opportunity['profit_margin'],
                'position_size': optimal_size,
                'execution_speed_risk': execution_speed_risk,
                'transfer_time_risk': transfer_time_risk,
                'total_costs': best_opportunity['total_costs'] * optimal_size
            }
        )
    
    def funding_rate_arbitrage(self, perp_funding_rate: float, current_price: float,
                             spot_price: float, funding_interval_hours: float = 8) -> StrategyResult:
        """
        Funding rate arbitrage between perpetual futures and spot
        Strategy from document: Spot arbitrage (Funding fee futures)
        """
        
        # Check if funding rate opportunity exists
        min_funding_threshold = 0.0001  # 0.01% minimum
        
        if abs(perp_funding_rate) < min_funding_threshold:
            return StrategyResult(
                "funding_rate_arbitrage", 0.3, 0, 0, 0, [], 
                f"Funding rate {perp_funding_rate:.4%} below threshold"
            )
        
        # Determine strategy based on funding rate
        if perp_funding_rate > 0:  # Long pays short - go short perp, long spot
            strategy_direction = "short_perp_long_spot"
            funding_income = True
        else:  # Short pays long - go long perp, short spot
            strategy_direction = "long_perp_short_spot" 
            funding_income = True
        
        # Calculate expected returns
        daily_funding_rate = abs(perp_funding_rate) * (24 / funding_interval_hours)
        annual_funding_rate = daily_funding_rate * 365
        
        position_size = 1.0  # 1 BTC position
        position_value = current_price * position_size
        
        # Daily funding income
        daily_funding_income = daily_funding_rate * position_value
        
        # Costs and risks
        trading_costs = position_value * 0.0002  # 0.02% trading fee estimate
        basis_risk = abs(current_price - spot_price) / current_price  # Price difference risk
        
        # Net daily return
        net_daily_return = daily_funding_income - (trading_costs / 30)  # Amortize trading costs
        
        # Risk assessment
        funding_volatility_risk = min(0.3, abs(perp_funding_rate) / 0.01)  # Higher funding = higher volatility
        basis_risk_score = min(0.2, basis_risk / 0.005)  # Scale to 0.5% basis risk
        
        # Strategy components (simplified for simulation)
        options_needed = []  # This strategy uses perps and spot, not options
        
        # Confidence scoring
        funding_attractiveness = min(1.0, abs(perp_funding_rate) / 0.005)  # Scale to 0.5% funding
        risk_adjusted_return = net_daily_return / max(0.01, basis_risk_score + funding_volatility_risk)
        sustainability = min(1.0, annual_funding_rate / 0.5)  # Sustainable if < 50% annually
        
        confidence_score = (
            funding_attractiveness * 0.4 +
            min(1.0, risk_adjusted_return / 10) * 0.3 +  # Scale to $10 daily return
            (1 - funding_volatility_risk) * 0.2 +
            sustainability * 0.1
        )
        
        return StrategyResult(
            strategy_name="funding_rate_arbitrage",
            confidence_score=confidence_score,
            expected_cost=trading_costs,
            expected_return=net_daily_return,
            max_loss=position_value * basis_risk,  # Maximum loss from basis risk
            options_needed=options_needed,
            reasoning=f"Funding rate arbitrage: {strategy_direction}. "
                     f"Funding rate: {perp_funding_rate:.4%}, Daily income: ${daily_funding_income:.2f}, "
                     f"Net daily return: ${net_daily_return:.2f}",
            risk_metrics={
                'funding_rate': perp_funding_rate,
                'daily_funding_rate': daily_funding_rate,
                'annual_funding_rate': annual_funding_rate,
                'daily_funding_income': daily_funding_income,
                'net_daily_return': net_daily_return,
                'basis_risk': basis_risk,
                'strategy_direction': strategy_direction,
                'funding_volatility_risk': funding_volatility_risk
            }
        )
    
    def calendar_spread_arbitrage(self, near_option_price: float, far_option_price: float,
                                 near_expiry_hours: float, far_expiry_hours: float,
                                 strike_price: float, current_price: float,
                                 volatility: float) -> StrategyResult:
        """
        Calendar spread arbitrage exploiting time decay inefficiencies
        """
        
        # Calculate theoretical price relationship
        time_ratio = near_expiry_hours / far_expiry_hours
        
        # Theoretical near option price based on far option
        theoretical_near_price = far_option_price * math.sqrt(time_ratio)
        price_discrepancy = near_option_price - theoretical_near_price
        discrepancy_pct = abs(price_discrepancy) / theoretical_near_price
        
        if discrepancy_pct < 0.05:  # Less than 5% discrepancy
            return StrategyResult(
                "calendar_spread_arbitrage", 0.3, 0, 0, 0, [], 
                f"Insufficient calendar spread discrepancy: {discrepancy_pct:.2%}"
            )
        
        # Determine strategy direction
        if price_discrepancy > 0:  # Near option overpriced
            strategy_type = "sell_near_buy_far"
            sell_option = "near"
            buy_option = "far"
        else:  # Near option underpriced
            strategy_type = "buy_near_sell_far"
            sell_option = "far"
            buy_option = "near"
        
        # Calculate position metrics
        position_size = 1.0
        
        if strategy_type == "sell_near_buy_far":
            net_cost = far_option_price - near_option_price
            max_profit = abs(price_discrepancy) * position_size
        else:
            net_cost = near_option_price - far_option_price
            max_profit = abs(price_discrepancy) * position_size
        
        # Time decay analysis
        near_theta_estimate = -near_option_price * 0.1  # Simplified theta estimate
        far_theta_estimate = -far_option_price * 0.05   # Slower decay for longer option
        
        daily_theta_profit = abs(near_theta_estimate - far_theta_estimate) * position_size
        
        options_needed = [
            {
                'type': 'call',  # Assume calls, but could be puts
                'strike': strike_price,
                'expiry_hours': near_expiry_hours,
                'quantity': position_size,
                'action': 'sell' if sell_option == "near" else 'buy',
                'estimated_premium': near_option_price,
                'greeks': {'theta': near_theta_estimate}
            },
            {
                'type': 'call',
                'strike': strike_price,
                'expiry_hours': far_expiry_hours,
                'quantity': position_size,
                'action': 'buy' if buy_option == "far" else 'sell',
                'estimated_premium': far_option_price,
                'greeks': {'theta': far_theta_estimate}
            }
        ]
        
        # Risk and confidence assessment
        time_risk = min(0.3, (far_expiry_hours - near_expiry_hours) / (24 * 7))  # Week normalization
        volatility_risk = min(0.2, volatility / 2.0)  # Scale to 200% vol
        
        discrepancy_significance = min(1.0, discrepancy_pct / 0.2)  # Scale to 20% max
        theta_advantage = min(1.0, daily_theta_profit / 5)  # Scale to $5 daily theta
        
        confidence_score = (
            discrepancy_significance * 0.4 +
            theta_advantage * 0.3 +
            (1 - time_risk) * 0.2 +
            (1 - volatility_risk) * 0.1
        )
        
        return StrategyResult(
            strategy_name="calendar_spread_arbitrage",
            confidence_score=confidence_score,
            expected_cost=max(0, net_cost),
            expected_return=max_profit + daily_theta_profit,
            max_loss=abs(net_cost),
            options_needed=options_needed,
            reasoning=f"Calendar spread arbitrage: {strategy_type}. "
                     f"Price discrepancy: {discrepancy_pct:.2%}, "
                     f"Daily theta profit: ${daily_theta_profit:.2f}",
            risk_metrics={
                'price_discrepancy': price_discrepancy,
                'discrepancy_pct': discrepancy_pct,
                'theoretical_near_price': theoretical_near_price,
                'daily_theta_profit': daily_theta_profit,
                'strategy_type': strategy_type,
                'time_risk': time_risk,
                'volatility_risk': volatility_risk
            }
        )
