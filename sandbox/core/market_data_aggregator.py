import asyncio
import time
import logging
import math
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from collections import deque
import statistics

from .price_feed_handler import PriceFeedHandler, AggregatedPrice
from ..utils.math_utils import calculate_realized_volatility, black_scholes_price

logger = logging.getLogger(__name__)

@dataclass
class MarketSnapshot:
    timestamp: float
    btc_price: float
    btc_volatility: float
    price_change_24h: float
    volume_24h: float
    funding_rates: Dict[str, float]
    option_chain: List[Dict]
    market_sentiment: str
    liquidity_score: float

@dataclass
class VolatilityMetrics:
    realized_vol_1h: float
    realized_vol_24h: float
    implied_vol_atm: float
    vol_skew: Dict[str, float]  # strike -> vol
    vol_term_structure: Dict[float, float]  # expiry_hours -> vol

class MarketDataAggregator:
    """Advanced market data aggregation with real-time analytics"""
    
    def __init__(self, price_feed_handler: PriceFeedHandler):
        self.price_feed = price_feed_handler
        self.price_history: deque = deque(maxlen=1440)  # 24 hours of minute data
        self.volatility_cache: Dict[str, VolatilityMetrics] = {}
        self.option_chains: Dict[str, List[Dict]] = {}
        self.funding_rates: Dict[str, float] = {}
        
        # Market state tracking
        self.last_snapshot: Optional[MarketSnapshot] = None
        self.update_interval = 60  # seconds
        self.running = False
        
        # Subscribe to price feed
        self.price_feed.subscribe(self._handle_price_update)
        
        # Volatility calculation parameters
        self.vol_lookback_periods = {
            '1h': 60,    # 60 minutes
            '24h': 1440, # 1440 minutes
            '7d': 10080  # 7 days
        }
    
    async def start(self):
        """Start market data aggregation"""
        if self.running:
            return
        
        self.running = True
        logger.info("Starting market data aggregator")
        
        # Start background tasks
        tasks = [
            asyncio.create_task(self._volatility_calculation_loop()),
            asyncio.create_task(self._option_chain_generator_loop()),
            asyncio.create_task(self._market_snapshot_loop())
        ]
        
        try:
            await asyncio.gather(*tasks)
        except Exception as e:
            logger.error(f"Error in market data aggregator: {e}")
            await self.stop()
    
    async def stop(self):
        """Stop market data aggregation"""
        self.running = False
        logger.info("Market data aggregator stopped")
    
    async def _handle_price_update(self, aggregated_data: Dict[str, AggregatedPrice]):
        """Handle incoming price updates"""
        try:
            if 'BTC-USD' in aggregated_data:
                btc_data = aggregated_data['BTC-USD']
                
                # Store price history
                price_point = {
                    'timestamp': btc_data.timestamp,
                    'price': btc_data.weighted_price,
                    'volume': btc_data.total_volume,
                    'spread': btc_data.max_price - btc_data.min_price,
                    'exchange_count': btc_data.exchange_count
                }
                
                self.price_history.append(price_point)
                
                # Update funding rates (mock data for demo)
                await self._update_funding_rates(btc_data.weighted_price)
                
        except Exception as e:
            logger.error(f"Error handling price update: {e}")
    
    async def _volatility_calculation_loop(self):
        """Calculate and update volatility metrics"""
        while self.running:
            try:
                if len(self.price_history) >= 60:  # Need at least 1 hour of data
                    await self._calculate_volatility_metrics()
                
                await asyncio.sleep(300)  # Update every 5 minutes
                
            except Exception as e:
                logger.error(f"Error in volatility calculation: {e}")
                await asyncio.sleep(60)
    
    async def _calculate_volatility_metrics(self):
        """Calculate comprehensive volatility metrics"""
        try:
            current_time = time.time()
            prices = [point['price'] for point in self.price_history]
            timestamps = [point['timestamp'] for point in self.price_history]
            
            # Calculate realized volatilities for different periods
            vol_metrics = {}
            
            for period, lookback in self.vol_lookback_periods.items():
                if len(prices) >= lookback:
                    recent_prices = prices[-lookback:]
                    recent_timestamps = timestamps[-lookback:]
                    
                    # Calculate returns
                    returns = []
                    for i in range(1, len(recent_prices)):
                        ret = math.log(recent_prices[i] / recent_prices[i-1])
                        returns.append(ret)
                    
                    if returns:
                        # Annualized volatility
                        period_vol = statistics.stdev(returns) * math.sqrt(525600)  # Minutes in a year
                        vol_metrics[f'realized_vol_{period}'] = period_vol
            
            # Generate implied volatility estimates
            current_price = prices[-1] if prices else 100000
            implied_vol_atm = self._estimate_implied_volatility(current_price)
            
            # Generate volatility skew
            vol_skew = self._generate_volatility_skew(current_price, implied_vol_atm)
            
            # Generate term structure
            vol_term_structure = self._generate_vol_term_structure(implied_vol_atm)
            
            # Store volatility metrics
            self.volatility_cache['BTC-USD'] = VolatilityMetrics(
                realized_vol_1h=vol_metrics.get('realized_vol_1h', 0.8),
                realized_vol_24h=vol_metrics.get('realized_vol_24h', 0.8),
                implied_vol_atm=implied_vol_atm,
                vol_skew=vol_skew,
                vol_term_structure=vol_term_structure
            )
            
            logger.debug(f"Updated volatility metrics: RV_1h={vol_metrics.get('realized_vol_1h', 0):.2f}, "
                        f"RV_24h={vol_metrics.get('realized_vol_24h', 0):.2f}, IV_ATM={implied_vol_atm:.2f}")
            
        except Exception as e:
            logger.error(f"Error calculating volatility metrics: {e}")
    
    def _estimate_implied_volatility(self, current_price: float) -> float:
        """Estimate implied volatility based on market conditions"""
        if len(self.price_history) < 60:
            return 0.8  # Default 80% for Bitcoin
        
        # Calculate recent price movements
        recent_prices = [point['price'] for point in list(self.price_history)[-60:]]
        price_changes = [abs(recent_prices[i] - recent_prices[i-1]) / recent_prices[i-1] 
                        for i in range(1, len(recent_prices))]
        
        # Base IV on recent volatility with adjustments
        base_vol = statistics.mean(price_changes) * math.sqrt(525600) if price_changes else 0.8
        
        # Apply market regime adjustments
        volume_factor = 1.0
        if self.price_history:
            recent_volume = statistics.mean([point.get('volume', 0) for point in list(self.price_history)[-10:]])
            if recent_volume > 50000:  # High volume
                volume_factor = 1.2
            elif recent_volume < 10000:  # Low volume
                volume_factor = 0.9
        
        # Trend factor
        trend_factor = 1.0
        if len(recent_prices) >= 20:
            price_trend = (recent_prices[-1] - recent_prices[-20]) / recent_prices[-20]
            if abs(price_trend) > 0.05:  # Strong trend
                trend_factor = 1.1
        
        estimated_iv = base_vol * volume_factor * trend_factor
        return max(0.2, min(3.0, estimated_iv))  # Clamp between 20% and 300%
    
    def _generate_volatility_skew(self, current_price: float, atm_vol: float) -> Dict[str, float]:
        """Generate volatility skew across strikes"""
        skew = {}
        
        # Typical Bitcoin volatility skew (put skew)
        strike_ranges = [0.9, 0.95, 0.98, 1.0, 1.02, 1.05, 1.1]
        
        for strike_ratio in strike_ranges:
            strike = current_price * strike_ratio
            
            # Bitcoin typically shows put skew
            if strike_ratio < 1.0:  # OTM puts
                skew_adjustment = (1.0 - strike_ratio) * 0.5  # Higher vol for lower strikes
            elif strike_ratio > 1.0:  # OTM calls
                skew_adjustment = (strike_ratio - 1.0) * 0.2  # Slightly higher vol for calls
            else:  # ATM
                skew_adjustment = 0.0
            
            skew[f"{strike:.0f}"] = atm_vol + skew_adjustment
        
        return skew
    
    def _generate_vol_term_structure(self, atm_vol: float) -> Dict[float, float]:
        """Generate volatility term structure"""
        term_structure = {}
        
        # Typical expiries in hours
        expiries = [2, 4, 8, 12, 24, 48, 168]  # 2h to 1 week
        
        for expiry in expiries:
            # Generally, shorter expiries have higher vol in crypto
            if expiry <= 4:
                vol_adjustment = 0.1  # Short-term premium
            elif expiry <= 24:
                vol_adjustment = 0.0  # Base vol
            else:
                vol_adjustment = -0.05  # Slight discount for longer term
            
            term_structure[expiry] = atm_vol + vol_adjustment
        
        return term_structure
    
    async def _option_chain_generator_loop(self):
        """Generate synthetic option chains for hedging strategies"""
        while self.running:
            try:
                await self._generate_option_chains()
                await asyncio.sleep(60)  # Update every minute
                
            except Exception as e:
                logger.error(f"Error generating option chains: {e}")
                await asyncio.sleep(60)
    
    async def _generate_option_chains(self):
        """Generate synthetic option chains"""
        try:
            if not self.price_history:
                return
            
            current_price = self.price_history[-1]['price']
            vol_metrics = self.volatility_cache.get('BTC-USD')
            
            if not vol_metrics:
                return
            
            option_chain = []
            
            # Generate options for different expiries
            expiries = [2, 4, 8, 12]  # hours
            
            for expiry_hours in expiries:
                expiry_vol = vol_metrics.vol_term_structure.get(expiry_hours, vol_metrics.implied_vol_atm)
                time_to_expiry = expiry_hours / 24 / 365
                
                # Generate strikes around current price
                strike_ratios = [0.95, 0.98, 1.0, 1.02, 1.05]
                
                for strike_ratio in strike_ratios:
                    strike = current_price * strike_ratio
                    
                    # Use skew-adjusted volatility
                    strike_vol = vol_metrics.vol_skew.get(f"{strike:.0f}", expiry_vol)
                    
                    # Calculate option prices
                    call_price = black_scholes_price(
                        spot=current_price,
                        strike=strike,
                        time_to_expiry=time_to_expiry,
                        risk_free_rate=0.05,
                        volatility=strike_vol,
                        option_type='call'
                    )
                    
                    put_price = black_scholes_price(
                        spot=current_price,
                        strike=strike,
                        time_to_expiry=time_to_expiry,
                        risk_free_rate=0.05,
                        volatility=strike_vol,
                        option_type='put'
                    )
                    
                    option_chain.extend([
                        {
                            'type': 'call',
                            'strike': strike,
                            'expiry_hours': expiry_hours,
                            'price': call_price,
                            'implied_vol': strike_vol,
                            'moneyness': strike_ratio
                        },
                        {
                            'type': 'put',
                            'strike': strike,
                            'expiry_hours': expiry_hours,
                            'price': put_price,
                            'implied_vol': strike_vol,
                            'moneyness': strike_ratio
                        }
                    ])
            
            self.option_chains['BTC-USD'] = option_chain
            
        except Exception as e:
            logger.error(f"Error generating option chains: {e}")
    
    async def _update_funding_rates(self, current_price: float):
        """Update synthetic funding rates"""
        try:
            # Generate synthetic funding rates based on price momentum
            if len(self.price_history) >= 8:
                recent_prices = [point['price'] for point in list(self.price_history)[-8:]]
                price_momentum = (recent_prices[-1] - recent_prices[0]) / recent_prices[0]
                
                # Mock funding rates for different exchanges
                base_funding = 0.0001  # 0.01% base
                momentum_adjustment = price_momentum * 0.1  # Scale momentum
                
                self.funding_rates = {
                    'okx': base_funding + momentum_adjustment + 0.00005,
                    'coinbase': base_funding + momentum_adjustment,
                    'kraken': base_funding + momentum_adjustment - 0.00005
                }
            
        except Exception as e:
            logger.error(f"Error updating funding rates: {e}")
    
    async def _market_snapshot_loop(self):
        """Generate periodic market snapshots"""
        while self.running:
            try:
                snapshot = await self._generate_market_snapshot()
                if snapshot:
                    self.last_snapshot = snapshot
                
                await asyncio.sleep(self.update_interval)
                
            except Exception as e:
                logger.error(f"Error generating market snapshot: {e}")
                await asyncio.sleep(60)
    
    async def _generate_market_snapshot(self) -> Optional[MarketSnapshot]:
        """Generate comprehensive market snapshot"""
        try:
            if not self.price_history:
                return None
            
            current_time = time.time()
            current_price = self.price_history[-1]['price']
            
            # Calculate 24h change
            price_24h_ago = None
            for point in reversed(self.price_history):
                if current_time - point['timestamp'] >= 86400:  # 24 hours
                    price_24h_ago = point['price']
                    break
            
            price_change_24h = 0.0
            if price_24h_ago:
                price_change_24h = (current_price - price_24h_ago) / price_24h_ago
            
            # Calculate 24h volume
            volume_24h = sum(point.get('volume', 0) for point in self.price_history 
                           if current_time - point['timestamp'] <= 86400)
            
            # Get volatility
            vol_metrics = self.volatility_cache.get('BTC-USD')
            btc_volatility = vol_metrics.realized_vol_24h if vol_metrics else 0.8
            
            # Market sentiment (simplified)
            market_sentiment = "neutral"
            if price_change_24h > 0.05:
                market_sentiment = "bullish"
            elif price_change_24h < -0.05:
                market_sentiment = "bearish"
            
            # Liquidity score (based on spread and volume)
            recent_spreads = [point.get('spread', 0) for point in list(self.price_history)[-10:]]
            avg_spread = statistics.mean(recent_spreads) if recent_spreads else 0
            spread_score = max(0, 1 - (avg_spread / current_price) / 0.001)  # Scale to 0.1% spread
            
            recent_volumes = [point.get('volume', 0) for point in list(self.price_history)[-10:]]
            avg_volume = statistics.mean(recent_volumes) if recent_volumes else 0
            volume_score = min(1.0, avg_volume / 50000)  # Scale to 50k volume
            
            liquidity_score = (spread_score + volume_score) / 2
            
            # Get option chain
            option_chain = self.option_chains.get('BTC-USD', [])
            
            return MarketSnapshot(
                timestamp=current_time,
                btc_price=current_price,
                btc_volatility=btc_volatility,
                price_change_24h=price_change_24h,
                volume_24h=volume_24h,
                funding_rates=self.funding_rates.copy(),
                option_chain=option_chain,
                market_sentiment=market_sentiment,
                liquidity_score=liquidity_score
            )
            
        except Exception as e:
            logger.error(f"Error generating market snapshot: {e}")
            return None
    
    def get_current_snapshot(self) -> Optional[MarketSnapshot]:
        """Get the latest market snapshot"""
        return self.last_snapshot
    
    def get_volatility_metrics(self, symbol: str = 'BTC-USD') -> Optional[VolatilityMetrics]:
        """Get volatility metrics for a symbol"""
        return self.volatility_cache.get(symbol)
    
    def get_option_chain(self, symbol: str = 'BTC-USD') -> List[Dict]:
        """Get option chain for a symbol"""
        return self.option_chains.get(symbol, [])
    
    def get_funding_rates(self) -> Dict[str, float]:
        """Get current funding rates"""
        return self.funding_rates.copy()
