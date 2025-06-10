import asyncio
import json
import time
import logging
import websockets
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, asdict
import statistics

logger = logging.getLogger(__name__)

@dataclass
class PriceData:
    symbol: str
    price: float
    timestamp: float
    exchange: str
    volume_24h: Optional[float] = None
    bid: Optional[float] = None
    ask: Optional[float] = None

@dataclass
class AggregatedPrice:
    symbol: str
    weighted_price: float
    median_price: float
    min_price: float
    max_price: float
    price_std: float
    timestamp: float
    exchange_count: int
    total_volume: float
    individual_prices: Dict[str, float]

class PriceFeedHandler:
    """Advanced price feed handler for multiple exchanges with real-time aggregation"""
    
    def __init__(self):
        self.price_data: Dict[str, Dict[str, PriceData]] = {}  # symbol -> exchange -> PriceData
        self.subscribers: List[Callable] = []
        self.running = False
        self.update_interval = 1.0  # seconds
        
        # Exchange configurations
        self.exchange_configs = {
            'coinbase': {
                'ws_url': 'wss://ws-feed.exchange.coinbase.com',
                'symbols': ['BTC-USD', 'ETH-USD'],
                'subscribe_message': {
                    "type": "subscribe",
                    "product_ids": ["BTC-USD"],
                    "channels": ["ticker"]
                }
            },
            'kraken': {
                'ws_url': 'wss://ws.kraken.com',
                'symbols': ['XBT/USD', 'ETH/USD'],
                'subscribe_message': {
                    "event": "subscribe",
                    "pair": ["XBT/USD"],
                    "subscription": {"name": "ticker"}
                }
            },
            'okx': {
                'ws_url': 'wss://ws.okx.com:8443/ws/v5/public',
                'symbols': ['BTC-USDT', 'ETH-USDT'],
                'subscribe_message': {
                    "op": "subscribe",
                    "args": [{"channel": "tickers", "instId": "BTC-USDT"}]
                }
            }
        }
        
        # WebSocket connections
        self.connections: Dict[str, Any] = {}
        
        # Price validation parameters
        self.max_price_deviation = 0.05  # 5% max deviation from median
        self.min_update_interval = 0.5   # Minimum time between updates
        self.last_update_time = 0
    
    async def start(self):
        """Start all exchange connections and price aggregation"""
        if self.running:
            return
        
        self.running = True
        logger.info("Starting price feed handler")
        
        # Start exchange connections
        tasks = []
        for exchange in self.exchange_configs.keys():
            task = asyncio.create_task(self._connect_exchange(exchange))
            tasks.append(task)
        
        # Start aggregation task
        aggregation_task = asyncio.create_task(self._aggregation_loop())
        tasks.append(aggregation_task)
        
        # Wait for all tasks
        try:
            await asyncio.gather(*tasks)
        except Exception as e:
            logger.error(f"Error in price feed handler: {e}")
            await self.stop()
    
    async def stop(self):
        """Stop all connections and tasks"""
        self.running = False
        
        # Close WebSocket connections
        for exchange, connection in self.connections.items():
            if connection and not connection.closed:
                await connection.close()
                logger.info(f"Closed {exchange} connection")
        
        self.connections.clear()
        logger.info("Price feed handler stopped")
    
    async def _connect_exchange(self, exchange: str):
        """Connect to a specific exchange WebSocket"""
        config = self.exchange_configs[exchange]
        max_retries = 5
        retry_delay = 5
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Connecting to {exchange} (attempt {attempt + 1})")
                
                connection = await websockets.connect(config['ws_url'])
                self.connections[exchange] = connection
                
                # Send subscription message
                await connection.send(json.dumps(config['subscribe_message']))
                logger.info(f"Subscribed to {exchange}")
                
                # Listen for messages
                async for message in connection:
                    if not self.running:
                        break
                    
                    try:
                        await self._process_message(exchange, message)
                    except Exception as e:
                        logger.error(f"Error processing message from {exchange}: {e}")
                
            except Exception as e:
                logger.error(f"Connection error for {exchange}: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    logger.error(f"Failed to connect to {exchange} after {max_retries} attempts")
    
    async def _process_message(self, exchange: str, message: str):
        """Process incoming WebSocket message from exchange"""
        try:
            data = json.loads(message)
            
            if exchange == 'coinbase':
                await self._process_coinbase_message(data)
            elif exchange == 'kraken':
                await self._process_kraken_message(data)
            elif exchange == 'okx':
                await self._process_okx_message(data)
                
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON from {exchange}: {message[:100]}...")
        except Exception as e:
            logger.error(f"Error processing {exchange} message: {e}")
    
    async def _process_coinbase_message(self, data: Dict):
        """Process Coinbase WebSocket message"""
        if data.get('type') == 'ticker':
            symbol = self._normalize_symbol(data.get('product_id', ''))
            price = float(data.get('price', 0))
            
            if symbol and price > 0:
                price_data = PriceData(
                    symbol=symbol,
                    price=price,
                    timestamp=time.time(),
                    exchange='coinbase',
                    volume_24h=float(data.get('volume_24h', 0)),
                    bid=float(data.get('best_bid', 0)) or None,
                    ask=float(data.get('best_ask', 0)) or None
                )
                
                await self._update_price_data(price_data)
    
    async def _process_kraken_message(self, data: Dict):
        """Process Kraken WebSocket message"""
        if isinstance(data, list) and len(data) >= 2:
            # Kraken ticker format: [channelID, data, channelName, pair]
            if len(data) >= 4 and data[2] == 'ticker':
                ticker_data = data[1]
                pair = data[3]
                symbol = self._normalize_symbol(pair)
                
                # Kraken ticker data format
                if 'c' in ticker_data:  # Last trade price
                    price = float(ticker_data['c'][0])
                    
                    if symbol and price > 0:
                        price_data = PriceData(
                            symbol=symbol,
                            price=price,
                            timestamp=time.time(),
                            exchange='kraken',
                            volume_24h=float(ticker_data.get('v', [0, 0])[1]),
                            bid=float(ticker_data.get('b', [0])[0]) or None,
                            ask=float(ticker_data.get('a', [0])[0]) or None
                        )
                        
                        await self._update_price_data(price_data)
    
    async def _process_okx_message(self, data: Dict):
        """Process OKX WebSocket message"""
        if data.get('arg', {}).get('channel') == 'tickers':
            ticker_list = data.get('data', [])
            
            for ticker in ticker_list:
                symbol = self._normalize_symbol(ticker.get('instId', ''))
                price = float(ticker.get('last', 0))
                
                if symbol and price > 0:
                    price_data = PriceData(
                        symbol=symbol,
                        price=price,
                        timestamp=time.time(),
                        exchange='okx',
                        volume_24h=float(ticker.get('vol24h', 0)),
                        bid=float(ticker.get('bidPx', 0)) or None,
                        ask=float(ticker.get('askPx', 0)) or None
                    )
                    
                    await self._update_price_data(price_data)
    
    def _normalize_symbol(self, symbol: str) -> str:
        """Normalize symbol names across exchanges"""
        symbol = symbol.upper()
        
        # Normalize to standard format
        if symbol in ['BTC-USD', 'XBT/USD', 'BTC-USDT', 'BTCUSD']:
            return 'BTC-USD'
        elif symbol in ['ETH-USD', 'ETH/USD', 'ETH-USDT', 'ETHUSD']:
            return 'ETH-USD'
        
        return symbol
    
    async def _update_price_data(self, price_data: PriceData):
        """Update internal price data storage"""
        symbol = price_data.symbol
        exchange = price_data.exchange
        
        # Initialize symbol data if needed
        if symbol not in self.price_data:
            self.price_data[symbol] = {}
        
        # Validate price data
        if self._validate_price_data(price_data):
            self.price_data[symbol][exchange] = price_data
            logger.debug(f"Updated {symbol} price from {exchange}: ${price_data.price:.2f}")
    
    def _validate_price_data(self, new_data: PriceData) -> bool:
        """Validate incoming price data for anomalies"""
        symbol = new_data.symbol
        
        # Check if we have existing data for comparison
        if symbol in self.price_data and self.price_data[symbol]:
            existing_prices = [data.price for data in self.price_data[symbol].values()]
            
            if existing_prices:
                median_price = statistics.median(existing_prices)
                deviation = abs(new_data.price - median_price) / median_price
                
                if deviation > self.max_price_deviation:
                    logger.warning(f"Price anomaly detected for {symbol} on {new_data.exchange}: "
                                 f"${new_data.price:.2f} vs median ${median_price:.2f} "
                                 f"({deviation:.2%} deviation)")
                    return False
        
        return True
    
    async def _aggregation_loop(self):
        """Main aggregation loop"""
        while self.running:
            try:
                current_time = time.time()
                
                if current_time - self.last_update_time >= self.min_update_interval:
                    aggregated_data = self._aggregate_prices()
                    
                    if aggregated_data:
                        await self._notify_subscribers(aggregated_data)
                        self.last_update_time = current_time
                
                await asyncio.sleep(self.update_interval)
                
            except Exception as e:
                logger.error(f"Error in aggregation loop: {e}")
                await asyncio.sleep(1)
    
    def _aggregate_prices(self) -> Optional[Dict[str, AggregatedPrice]]:
        """Aggregate prices from all exchanges"""
        aggregated = {}
        current_time = time.time()
        
        for symbol, exchange_data in self.price_data.items():
            if not exchange_data:
                continue
            
            # Filter recent data (within last 30 seconds)
            recent_data = {
                exchange: data for exchange, data in exchange_data.items()
                if current_time - data.timestamp <= 30
            }
            
            if len(recent_data) < 1:
                continue
            
            prices = [data.price for data in recent_data.values()]
            volumes = [data.volume_24h for data in recent_data.values() if data.volume_24h]
            
            # Calculate weighted average price (by volume if available)
            if volumes and len(volumes) == len(prices):
                total_volume = sum(volumes)
                if total_volume > 0:
                    weighted_price = sum(p * v for p, v in zip(prices, volumes)) / total_volume
                else:
                    weighted_price = statistics.mean(prices)
            else:
                weighted_price = statistics.mean(prices)
            
            # Calculate statistics
            median_price = statistics.median(prices)
            min_price = min(prices)
            max_price = max(prices)
            price_std = statistics.stdev(prices) if len(prices) > 1 else 0.0
            
            aggregated[symbol] = AggregatedPrice(
                symbol=symbol,
                weighted_price=weighted_price,
                median_price=median_price,
                min_price=min_price,
                max_price=max_price,
                price_std=price_std,
                timestamp=current_time,
                exchange_count=len(recent_data),
                total_volume=sum(volumes) if volumes else 0,
                individual_prices={exchange: data.price for exchange, data in recent_data.items()}
            )
        
        return aggregated if aggregated else None
    
    async def _notify_subscribers(self, aggregated_data: Dict[str, AggregatedPrice]):
        """Notify all subscribers of price updates"""
        for subscriber in self.subscribers:
            try:
                if asyncio.iscoroutinefunction(subscriber):
                    await subscriber(aggregated_data)
                else:
                    subscriber(aggregated_data)
            except Exception as e:
                logger.error(f"Error notifying subscriber: {e}")
    
    def subscribe(self, callback: Callable):
        """Subscribe to price updates"""
        self.subscribers.append(callback)
    
    def unsubscribe(self, callback: Callable):
        """Unsubscribe from price updates"""
        if callback in self.subscribers:
            self.subscribers.remove(callback)
    
    def get_latest_price(self, symbol: str) -> Optional[AggregatedPrice]:
        """Get latest aggregated price for a symbol"""
        if symbol in self.price_data:
            # Generate current aggregation for the symbol
            current_time = time.time()
            exchange_data = self.price_data[symbol]
            
            recent_data = {
                exchange: data for exchange, data in exchange_data.items()
                if current_time - data.timestamp <= 30
            }
            
            if recent_data:
                prices = [data.price for data in recent_data.values()]
                volumes = [data.volume_24h for data in recent_data.values() if data.volume_24h]
                
                if volumes and len(volumes) == len(prices):
                    total_volume = sum(volumes)
                    weighted_price = sum(p * v for p, v in zip(prices, volumes)) / total_volume if total_volume > 0 else statistics.mean(prices)
                else:
                    weighted_price = statistics.mean(prices)
                
                return AggregatedPrice(
                    symbol=symbol,
                    weighted_price=weighted_price,
                    median_price=statistics.median(prices),
                    min_price=min(prices),
                    max_price=max(prices),
                    price_std=statistics.stdev(prices) if len(prices) > 1 else 0.0,
                    timestamp=current_time,
                    exchange_count=len(recent_data),
                    total_volume=sum(volumes) if volumes else 0,
                    individual_prices={exchange: data.price for exchange, data in recent_data.items()}
                )
        
        return None
    
    def get_price_history(self, symbol: str, hours: int = 1) -> List[PriceData]:
        """Get price history for a symbol"""
        # This would typically be stored in a database
        # For now, return current data from all exchanges
        if symbol in self.price_data:
            return list(self.price_data[symbol].values())
        return []
