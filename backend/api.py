# backend/api.py

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Union
import json
import asyncio
import time
import logging
import math
import uuid
import os
from threading import Thread
import queue

# --- CORE IMPORTS ---
from backend import config # Your main configuration file
from backend.advanced_pricing_engine import AdvancedPricingEngine
from backend.volatility_engine import AdvancedVolatilityEngine
from backend.alpha_signals import AlphaSignalGenerator
from backend.portfolio_hedger import PortfolioHedger
from backend.trade_executor import TradeExecutor, TradeOrder, OrderSide, UserAccount
from backend.data_feed_manager import DataFeedManager
from backend.utils import setup_logger # Your logging utility

# Add this import for SandboxService
from sandbox.api.websocket_extension import SandboxService

# Conditional imports
try:
    from backend.rl_hedger import RLHedger
    RL_HEDGER_AVAILABLE = True
except ImportError:
    RL_HEDGER_AVAILABLE = False

if getattr(config, 'SENTIMENT_ANALYSIS_ENABLED', False):
    try:
        from backend.sentiment_analyzer import SentimentAnalyzer
        SENTIMENT_ANALYZER_AVAILABLE = True
    except ImportError:
        SENTIMENT_ANALYZER_AVAILABLE = False
else:
    SENTIMENT_ANALYZER_AVAILABLE = False

# Import the dedicated price WebSocket module
from backend import ws_price

# Setup Logger
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logger = setup_logger(__name__)

# --- THREAD-SAFE EVENT LOOP FIX ---
# Global queue for price updates
price_queue = queue.Queue()
active_connections = set()
main_loop = None

async def broadcast_price_update(price: float, volume: float):
    """Actual broadcast function - runs in main event loop"""
    if not active_connections:
        return
        
    payload = {"type": "price_update", "data": {"price": price, "volume": volume}}
    disconnected = set()
    
    for ws in active_connections:
        try:
            await ws.send_json(payload)
        except Exception:
            disconnected.add(ws)
    
    active_connections.difference_update(disconnected)
    logging.info(f"📊 Broadcasted to {len(active_connections)} clients: ${price:,.2f}")

async def price_queue_processor():
    """Background task that processes queued price updates"""
    while True:
        try:
            if not price_queue.empty():
                price, volume = price_queue.get_nowait()
                await broadcast_price_update(price, volume)
            await asyncio.sleep(0.1)  # Check queue every 100ms
        except Exception as e:
            logging.error(f"Price queue processor error: {e}")
            await asyncio.sleep(1)

def process_price_update_sync(price: float, volume: float):
    """Thread-safe function called from sync price feed"""
    try:
        # Put price update in queue - this is thread-safe
        price_queue.put_nowait((price, volume))
        logging.info(f"📊 Queued price update: ${price:,.2f}")
    except queue.Full:
        logging.warning("Price queue full - skipping update")
    except Exception as e:
        logging.error(f"Failed to queue price update: {e}")

# --- Pydantic Models ---
class OptionIdentifier(BaseModel):
    symbol: str
    option_type: str = Field(..., pattern="^(call|put)$")
    strike: float
    expiry_minutes: int

class TradeRequest(BaseModel):
    user_id: str
    option_type: str = Field(..., pattern="^(call|put)$")
    strike: float
    expiry_minutes: int
    quantity: float
    side: str = Field(..., pattern="^(buy|sell)$")
    # premium_per_contract: Optional[float] = None # Only if frontend reliably sends it and backend validates/uses it

class UserAccountRequest(BaseModel):
    user_id: str
    initial_btc_balance: float = 0.01

class ClosePositionRequest(BaseModel):
    user_id: str
    position_id: str
    partial_quantity: Optional[float] = None

class BlackScholesRequest(BaseModel):
    current_price: float
    strike_price: float
    time_to_expiry_years: float
    option_type: str = Field(..., pattern="^(call|put)$")
    risk_free_rate: Optional[float] = None
    volatility: Optional[float] = None

# New Pydantic model for synthetic account updates
class SyntheticAccountUpdate(BaseModel):
    account_id: str
    platform: str
    positions: List[Dict]

# --- FastAPI Application Setup ---
app = FastAPI(
    title=f"{config.PLATFORM_NAME} API",
    version=config.VERSION,
    docs_url="/docs",
    redoc_url="/redoc"
)

# --- BULLET-PROOF CORS SETUP ---
from backend.cors_config import setup_cors
setup_cors(app)
logger.info("✅ Bullet-proof CORS middleware configured")

@app.middleware("http")
async def log_requests_middleware(request: Request, call_next):
    start_time = time.perf_counter()
    response = await call_next(request)
    process_time = time.perf_counter() - start_time
    if process_time > 0.1: # Log only if request is slower than 100ms
        logger.warning(f"⚠️ Slow request: {request.method} {request.url.path} took {process_time:.3f}s")
    return response

# +++ ADDED: asyncio.Event for startup synchronization +++
api_startup_complete_event = asyncio.Event()
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++

# --- WebSocket Manager ---
class SimpleWebSocketManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.user_connections: Dict[str, WebSocket] = {}
        self._lock = asyncio.Lock() # For thread-safe modifications if needed, though FastAPI runs in single event loop

    async def connect(self, websocket: WebSocket, user_id: Optional[str] = None):
        # CRITICAL FIX: DO NOT accept the connection here.
        # The main endpoint will handle that. This method only tracks the connection.
        # await websocket.accept()  <-- REMOVED THIS LINE
        
        async with self._lock:
            self.active_connections.append(websocket)
            if user_id: self.user_connections[user_id] = websocket
        logger.info(f"🔌 WebSocket tracked (Total: {len(self.active_connections)}, Users: {len(self.user_connections)})")

    async def disconnect(self, websocket: WebSocket, user_id: Optional[str] = None):
        async with self._lock:
            if websocket in self.active_connections: self.active_connections.remove(websocket)
            if user_id and user_id in self.user_connections and self.user_connections[user_id] == websocket:
                del self.user_connections[user_id]
        logger.info(f"🔌 WebSocket disconnected (Total: {len(self.active_connections)}, Users: {len(self.user_connections)})")

    async def broadcast_safe(self, message: dict, user_id: Optional[str] = None):
        message_json = json.dumps(message)
        targets: List[WebSocket] = []

        async with self._lock: # Access shared lists safely
            if user_id and user_id in self.user_connections:
                targets.append(self.user_connections[user_id])
            elif not user_id:
                targets = self.active_connections.copy()

        if not targets: return

        disconnected_sockets_info: List[tuple[WebSocket, Optional[str]]] = []
        for ws_client in targets:
            try:
                await ws_client.send_text(message_json)
            except Exception:
                logger.debug(f"WebSocket send failed to a client. Marking for removal.")
                # Try to find the user_id associated with this failing ws_client for proper disconnect
                uid_of_failed_socket = None
                async with self._lock: # Lock for reading user_connections if needed, though less critical here
                    for uid, sock in self.user_connections.items():
                        if sock == ws_client:
                            uid_of_failed_socket = uid
                            break
                disconnected_sockets_info.append((ws_client, uid_of_failed_socket))
        
        for ws_client_to_remove, uid_to_remove in disconnected_sockets_info:
            await self.disconnect(ws_client_to_remove, uid_to_remove)

ws_manager_global_instance = SimpleWebSocketManager() # Global instance of the manager for app.state

# --- Price Update Handling Factory ---
def _handle_price_update_sync_factory(app_instance: FastAPI):
    # This function needs to be a closure to capture app_instance
    # if it's called by DataFeedManager which doesn't know about app_instance.
    # It stores the latest price on itself for the health check.
    def _handle_price_update_sync(price_data):
        try:
            pricing_engine_instance = getattr(app_instance.state, 'pricing_engine', None)
            if pricing_engine_instance:
                price_val = getattr(price_data, 'price', 0.0)
                volume_val = getattr(price_data, 'volume', 0.0)
                if price_val > 0:
                    logger.info(f"📊 Processing price update: ${price_val:,.2f} (volume: {volume_val:,.0f})")
                    pricing_engine_instance.update_market_data(price_val, volume_val)
                    _handle_price_update_sync.latest_price = price_val # Store on function object
                    
                    # --- THREAD-SAFE EVENT LOOP FIX ---
                    # Use thread-safe queue instead of problematic async call
                    process_price_update_sync(price_val, volume_val)
                    # --- END THREAD-SAFE EVENT LOOP FIX ---
                else:
                    logger.warning(f"Invalid price value received: {price_val}")
                        
        except Exception as e:
            logger.error(f"Error in price update handler: {e}")
    
    return _handle_price_update_sync

# --- Stock Prompts for Simple Chat ---
STOCK_PROMPTS = {
    "atm_itm_otm": {
        "question": "What is the difference between ATM, ITM, and OTM?",
        "answer": "ATM (At-The-Money): Strike price equals current market price. ITM (In-The-Money): Option has intrinsic value (call: strike < market price, put: strike > market price). OTM (Out-of-The-Money): Option has no intrinsic value (call: strike > market price, put: strike < market price)."
    },
    "greeks": {
        "question": "What are the Greeks in options trading?",
        "answer": "Delta: Price change of option per $1 change in underlying. Gamma: Rate of change of delta. Theta: Time decay of option value. Vega: Sensitivity to volatility changes. Rho: Sensitivity to interest rate changes."
    },
    "implied_volatility": {
        "question": "What is implied volatility?",
        "answer": "Implied volatility is the market's expectation of future price volatility, derived from option prices. Higher IV means higher option premiums due to expected larger price swings."
    },
    "time_decay": {
        "question": "How does time decay affect options?",
        "answer": "Options lose value as expiration approaches (theta decay). This accelerates as expiration gets closer, especially for ATM options. Time decay is why many options expire worthless."
    },
    "risk_management": {
        "question": "What are key risk management strategies for options?",
        "answer": "1) Position sizing: Never risk more than 1-2% of capital per trade. 2) Stop losses: Set clear exit points. 3) Diversification: Don't concentrate in one direction. 4) Understand max loss: Know your worst-case scenario before entering."
    }
}

# --- FastAPI Startup Event ---
@app.on_event("startup")
async def startup_event():
    """Initialize components when the application starts up."""
    logger.info("Starting up API components...")
    try:
        # Initialize WebSocket manager
        app.state.ws_manager = SimpleWebSocketManager()
        logger.info("✅ WebSocket manager initialized.")

        # Initialize pricing engine
        app.state.pricing_engine = AdvancedPricingEngine(
            volatility_engine=AdvancedVolatilityEngine(),
            alpha_signal_generator=AlphaSignalGenerator()
        )
        logger.info("✅ Pricing engine initialized.")

        # Initialize data feed manager
        app.state.data_feed_manager = DataFeedManager()
        app.state.data_feed_manager.add_price_callback(_handle_price_update_sync_factory(app))
        app.state.data_feed_manager.start()
        logger.info("✅ Data feed manager started.")

        # Initialize hedger
        app.state.hedger = PortfolioHedger(pricing_engine=app.state.pricing_engine)
        logger.info("✅ Hedger initialized.")

        # Initialize trade executor
        app.state.trade_executor = TradeExecutor(
            pricing_engine=app.state.pricing_engine,
            hedger=app.state.hedger
        )
        logger.info("✅ Trade executor initialized.")

        # Initialize sandbox service with trade executor
        app.state.sandbox_service = SandboxService(
            data_hub=app.state.data_feed_manager,
            pricing_engine=app.state.pricing_engine,
            trade_executor=app.state.trade_executor
        )
        app.state.sandbox_service.start()
        logger.info("✅ Sandbox service started.")

        # Start background tasks
        loop = asyncio.get_running_loop()
        app.state.position_updates_task = loop.create_task(background_position_updates(app))
        app.state.market_updates_task = loop.create_task(background_market_updates(app))
        
        # --- THREAD-SAFE EVENT LOOP FIX ---
        global main_loop
        main_loop = loop
        asyncio.create_task(price_queue_processor())
        logger.info("🚀 Price queue processor started")
        # --- END THREAD-SAFE EVENT LOOP FIX ---
        
        logger.info("✅ Background tasks started.")

        # Set the startup complete event
        api_startup_complete_event.set()
        logger.info("✅ API startup complete event set.")

    except Exception as e:
        logger.error(f"❌ API Startup failed critically: {e}", exc_info=True)
        # Set event even on failure to prevent hanging
        api_startup_complete_event.set()
        raise RuntimeError(f"API Startup failed: {e}")

# --- Background Tasks ---
async def background_position_updates(app_instance: FastAPI):
    """Background task to update position data and broadcast to WebSocket clients."""
    logger.info("Background position updates task started.")
    while True:
        try:
            await asyncio.sleep(5.0)  # Update every 5 seconds
            trade_executor = getattr(app_instance.state, 'trade_executor', None)
            if not trade_executor:
                continue

            for user_id, account in trade_executor.user_accounts.items():
                ws_manager = getattr(app_instance.state, 'ws_manager', None)
                if ws_manager:
                    await ws_manager.broadcast_safe({
                        "type": "position_update",
                        "data": {
                            "user_id": user_id,
                            "portfolio": account.get_portfolio_summary()
                        }
                    }, user_id=user_id)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error in background position updates: {e}", exc_info=True)

async def background_market_updates(app_instance: FastAPI):
    """Background task to update market data and broadcast to WebSocket clients."""
    logger.info("🚀 Background market updates task started.")
    update_count = 0
    while True:
        try:
            await asyncio.sleep(1.0) # Broadcasting every second
            data_feed_manager = getattr(app_instance.state, 'data_feed_manager', None)
            
            # This check is critical - if the data feed stops, so do updates
            if not data_feed_manager or not data_feed_manager.is_running:
                logger.warning("⚠️ Data feed manager not available or not running")
                continue

            current_price = data_feed_manager.get_current_price()
            if current_price and current_price > 0:
                ws_manager = getattr(app_instance.state, 'ws_manager', None)
                if ws_manager:
                    # This broadcast sends the ongoing updates
                    update_count += 1
                    await ws_manager.broadcast_safe({
                        "type": "market_update",
                        "data": {
                            "price": current_price,
                            "timestamp": time.time()
                        }
                    })
                    logger.info(f"📊 Market update #{update_count}: ${current_price:,.2f} broadcasted to {len(ws_manager.active_connections)} clients")
                else:
                    logger.warning("⚠️ WebSocket manager not available")
            else:
                logger.warning(f"⚠️ Invalid price received: {current_price}")

        except asyncio.CancelledError:
            logger.info("🛑 Background market updates task cancelled")
            break
        except Exception as e:
            logger.error(f"❌ Error in background market updates: {e}", exc_info=True)

# --- API Endpoints ---
@app.get("/")
async def health_check_endpoint(request: Request):
    """Health check endpoint."""
    return {"status": "ok", "version": config.VERSION}

@app.post("/blackscholes/calculate")
async def calculate_black_scholes_basic_endpoint(request_data: BlackScholesRequest, request: Request):
    """Calculate basic Black-Scholes option price."""
    try:
        pricing_engine = getattr(request.app.state, 'pricing_engine', None)
        if not pricing_engine:
            raise HTTPException(status_code=503, detail="Pricing engine not available.")
        price = pricing_engine.calculate_option_price(
            request_data.current_price,
            request_data.strike_price,
            request_data.time_to_expiry_years,
            request_data.volatility or pricing_engine.current_volatility,
            request_data.option_type,
            request_data.risk_free_rate
        )
        return {"price": price}
    except Exception as e_bs_calc:
        logger.error(f"Basic Black-Scholes calculation error: {e_bs_calc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Calculation error: {str(e_bs_calc)}")

@app.get("/market/price")
async def get_current_market_price_endpoint(request: Request):
    local_data_feed_manager = getattr(request.app.state, 'data_feed_manager', None)
    local_pricing_engine = getattr(request.app.state, 'pricing_engine', None)
    price_update_callback_ref = _handle_price_update_sync_factory(request.app)

    if not local_data_feed_manager or not local_data_feed_manager.is_running:
        raise HTTPException(status_code=503, detail="Data feed unavailable or not currently running.")
    
    current_market_price_val = local_data_feed_manager.get_current_price()
    if not (current_market_price_val and current_market_price_val > 0):
        current_market_price_val = local_pricing_engine.current_price if local_pricing_engine and local_pricing_engine.current_price > 0 else getattr(price_update_callback_ref, 'latest_price', 0.0)
    
    return {"price": current_market_price_val, "timestamp": time.time(),
            "exchange_status": local_data_feed_manager.get_exchange_status() if local_data_feed_manager else "unknown"}

@app.get("/market/option-chains")
async def get_option_chains_endpoint(request: Request, expiry_minutes: Optional[int] = None):
    local_pricing_engine = getattr(request.app.state, 'pricing_engine', None)
    if not local_pricing_engine:
        raise HTTPException(status_code=503, detail="Pricing engine not available.")
    if not (local_pricing_engine.current_price and local_pricing_engine.current_price > 0):
        logger.debug("Option chains: current_price not yet in pricing_engine. Waiting briefly...")
        await asyncio.sleep(0.5) 
        if not (local_pricing_engine.current_price and local_pricing_engine.current_price > 0):
            logger.error("Market price still not available for pricing engine after wait. Cannot generate chains.")
            raise HTTPException(status_code=503, detail="Market price not yet available for pricing engine.")
    try:
        if expiry_minutes:
            if expiry_minutes not in config.AVAILABLE_EXPIRIES_MINUTES:
                raise HTTPException(status_code=400, detail=f"Invalid expiry. Available: {config.AVAILABLE_EXPIRIES_MINUTES}")
            chain_result = local_pricing_engine.generate_option_chain(expiry_minutes)
            return {"chains": {str(expiry_minutes): chain_result.dict() if chain_result else {}}}
        else:
            all_chains_result = local_pricing_engine.generate_all_chains()
            return {"chains": {str(key): val.dict() if val else {} for key, val in all_chains_result.items()}}
    except Exception as e_chains:
        logger.error(f"❌ Error generating option chains: {e_chains}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error generating option chains: {str(e_chains)}")

@app.post("/trades/execute")
async def execute_trade_endpoint(trade_request: TradeRequest, request_obj: Request, background_tasks: BackgroundTasks): # Changed param names
    local_trade_executor = getattr(request_obj.app.state, 'trade_executor', None)
    local_pricing_engine = getattr(request_obj.app.state, 'pricing_engine', None)
    local_ws_manager = getattr(request_obj.app.state, 'ws_manager', None)

    if not (local_trade_executor and local_pricing_engine and local_pricing_engine.current_price and local_pricing_engine.current_price > 0):
        raise HTTPException(status_code=503, detail="System not ready for trading or market price unavailable.")
    try:
        option_chain_data = local_pricing_engine.generate_option_chain(trade_request.expiry_minutes)
        if not option_chain_data:
            raise HTTPException(status_code=400, detail=f"No option chain available for expiry {trade_request.expiry_minutes} min.")
        
        quotes_list = option_chain_data.calls if trade_request.option_type.lower() == "call" else option_chain_data.puts
        matching_quote = next((q for q in quotes_list if math.isclose(q.strike, trade_request.strike)), None)

        if not matching_quote:
            available_strikes = [q.strike for q in quotes_list]
            logger.warning(f"Trade Execution: Strike price ${trade_request.strike} not found for {trade_request.option_type} with {trade_request.expiry_minutes} min expiry. Available strikes: {available_strikes}. Current BTC: {local_pricing_engine.current_price}")
            raise HTTPException(status_code=400, detail=f"Strike price ${trade_request.strike} not found for {trade_request.option_type} with {trade_request.expiry_minutes} min expiry. Ensure strike exists in current market conditions.")
        
        greeks_for_order = matching_quote.greeks if isinstance(matching_quote.greeks, dict) else {}
        order_details = TradeOrder(
            order_id=f"ord_{int(time.time()*1000)}_{trade_request.user_id[-4:] if len(trade_request.user_id)>=4 else trade_request.user_id}",
            user_id=trade_request.user_id, symbol=matching_quote.symbol, side=OrderSide(trade_request.side.lower()),
            quantity=trade_request.quantity, premium_per_contract=matching_quote.premium_usd,
            total_premium=(matching_quote.premium_usd * trade_request.quantity), option_type=trade_request.option_type,
            strike=trade_request.strike, expiry_minutes=trade_request.expiry_minutes, timestamp=time.time(),
            greeks=greeks_for_order
        )
        
        success_flag, message_str, position_instance_obj = local_trade_executor.execute_trade(order_details)
        if not success_flag:
            raise HTTPException(status_code=400, detail=message_str)
        
        if local_ws_manager:
            background_tasks.add_task(local_ws_manager.broadcast_safe, {
                "type":"trade_executed",
                "data":{"order_id":order_details.order_id, "symbol":order_details.symbol,
                        "premium":order_details.total_premium,
                        "position_id":position_instance_obj.position_id if position_instance_obj else None}
            }, user_id=trade_request.user_id)
        
        return {
            "success":True, "message":message_str, "order_id":order_details.order_id,
            "position_id":position_instance_obj.position_id if position_instance_obj else None,
            "premium_total":order_details.total_premium, "side":order_details.side.value
        }
    except HTTPException: 
        raise
    except Exception as e_trade_exec:
        logger.error(f"❌ Trade execution error: {e_trade_exec}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Trade execution failed: {str(e_trade_exec)}")

@app.post("/users/create")
async def create_user_endpoint(user_request: UserAccountRequest, request_obj: Request) -> UserAccount: # Changed param names
    local_trade_executor = getattr(request_obj.app.state, 'trade_executor', None)
    if not local_trade_executor: raise HTTPException(status_code=503, detail="Trade executor not available")
    try:
        if user_request.user_id in local_trade_executor.user_accounts:
            raise HTTPException(status_code=400, detail=f"User {user_request.user_id} already exists.")
        account_obj = local_trade_executor.create_user_account(user_request.user_id, user_request.initial_btc_balance)
        return account_obj 
    except HTTPException: raise
    except Exception as e: logger.error(f"User creation error: {e}", exc_info=True); raise HTTPException(status_code=500, detail=f"User creation failed: {str(e)}")

@app.get("/users/{user_id}/portfolio")
async def get_portfolio_endpoint(user_id: str, request: Request):
    local_trade_executor = getattr(request.app.state, 'trade_executor', None)
    if not local_trade_executor: raise HTTPException(status_code=503, detail="Trade executor not available")
    portfolio_data = local_trade_executor.get_user_portfolio_summary(user_id) 
    if not portfolio_data: raise HTTPException(status_code=404, detail=f"User {user_id} not found or no portfolio.")
    return portfolio_data

@app.post("/positions/close")
async def close_position_endpoint(close_request: ClosePositionRequest, request_obj: Request, background_tasks: BackgroundTasks): # Changed param names
    local_trade_executor = getattr(request_obj.app.state, 'trade_executor', None)
    local_ws_manager = getattr(request_obj.app.state, 'ws_manager', None)
    if not local_trade_executor: raise HTTPException(status_code=503, detail="Trade executor not available")
    try:
        success_flag, message_str = local_trade_executor.close_position(close_request.user_id, close_request.position_id, close_request.partial_quantity)
        if not success_flag: raise HTTPException(status_code=400, detail=message_str)
        if local_ws_manager:
            background_tasks.add_task(local_ws_manager.broadcast_safe, {"type":"position_closed", "data":{"position_id":close_request.position_id, "message":message_str}}, user_id=close_request.user_id)
        return {"success":True, "message":message_str}
    except HTTPException: raise
    except Exception as e: logger.error(f"Position close error: {e}", exc_info=True); raise HTTPException(status_code=500, detail=f"Position close failed: {str(e)}")

# +++ DEFINITIVE WebSocket endpoint with defensive send operations +++
@app.websocket("/ws")
async def websocket_connection_endpoint(websocket: WebSocket, user_id: Optional[str] = None):
    local_ws_manager = getattr(websocket.app.state, 'ws_manager', None)
    local_pricing_engine = getattr(websocket.app.state, 'pricing_engine', None)

    if not local_ws_manager:
        logger.error("WebSocket connection failed: ws_manager not found.")
        await websocket.accept()
        await websocket.close(code=1011, reason="Server-side WebSocket manager not available")
        return

    # Accept the connection first
    await websocket.accept()
    await local_ws_manager.connect(websocket, user_id)
    
    try:
        # Send initial connection message
        initial_price = local_pricing_engine.current_price if local_pricing_engine else 0.0
        await websocket.send_text(json.dumps({
            "type": "connected",
            "data": {"current_price": initial_price}
        }))
        logger.info(f"Sent 'connected' message with initial price ${initial_price} to client.")

        # Main loop for receiving messages and sending keep-alives
        while True:
            try:
                # Wait for a message from the client with a timeout
                data_received = await asyncio.wait_for(websocket.receive_text(), timeout=config.WEBSOCKET_TIMEOUT_SECONDS)
                message_obj = json.loads(data_received)

                # Process 'join' message
                if message_obj.get("type") == "join":
                    logger.info(f"Client sent 'join' message: {message_obj.get('data')}")
                    # Defensively try to send acknowledgment
                    try:
                        await websocket.send_text(json.dumps({"type": "acknowledged", "data": "Join message received"}))
                    except Exception as e:
                        if "ConnectionClosed" in str(e) or "Connection closed" in str(e):
                            logger.warning("Could not send 'join' ack; client disconnected. Breaking loop.")
                            break
                        else:
                            raise e

                # Process 'ping' message
                elif message_obj.get("type") == "ping":
                    try:
                        await websocket.send_text(json.dumps({"type": "pong", "timestamp": time.time()}))
                    except Exception as e:
                        if "ConnectionClosed" in str(e) or "Connection closed" in str(e):
                            logger.warning("Could not send 'pong'; client disconnected. Breaking loop.")
                            break
                        else:
                            raise e

            except asyncio.TimeoutError:
                # If client is silent, send a keep-alive to prevent timeout
                try:
                    await websocket.send_text(json.dumps({"type": "keepalive", "timestamp": time.time()}))
                except Exception as e:
                    if "ConnectionClosed" in str(e) or "Connection closed" in str(e):
                        logger.warning("Could not send 'keepalive'; client disconnected. Breaking loop.")
                        break
                    else:
                        raise e
            
            except WebSocketDisconnect:
                logger.info("WebSocketDisconnect exception caught. Client has disconnected.")
                break # Exit the loop gracefully

            except json.JSONDecodeError:
                logger.warning("Received invalid JSON from WebSocket client.")
                # Continue loop to wait for next valid message
                continue

            # This exception is the one you are seeing in the logs
            except Exception as e:
                if "ConnectionClosedOK" in str(e) or "Connection closed" in str(e):
                    logger.info("ConnectionClosedOK exception caught. Client has disconnected cleanly.")
                    break
                else:
                    logger.error(f"An unexpected error occurred in WebSocket loop: {e}", exc_info=True)
                    break

    except Exception as e_conn:
        # Catch any other unexpected errors during the connection's lifecycle
        if "ConnectionClosed" in str(e_conn) or "Connection closed" in str(e_conn):
            logger.info("Connection closed by client during connection lifecycle.")
        else:
            logger.error(f"Top-level WebSocket error: {e_conn}", exc_info=True)
    
    finally:
        # This cleanup will always run
        await local_ws_manager.disconnect(websocket, user_id)
        logger.info("WebSocket connection cleanup complete.")
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

# New endpoint to update synthetic account information
@app.post("/sandbox/update-account")
async def update_synthetic_account_endpoint(account_update: SyntheticAccountUpdate):
    """Update synthetic account information."""
    try:
        # Ensure the directory exists
        os.makedirs('sandbox/config', exist_ok=True)
        
        # Initialize file if it doesn't exist
        if not os.path.exists('sandbox/config/synthetic_accounts.json'):
            with open('sandbox/config/synthetic_accounts.json', 'w') as f:
                json.dump({"accounts": []}, f, indent=2)
        
        # Load current accounts
        with open('sandbox/config/synthetic_accounts.json', 'r') as f:
            data = json.load(f)
        
        # Update the account
        account_updated = False
        for acc in data['accounts']:
            if acc['account_id'] == account_update.account_id:
                acc['platform'] = account_update.platform
                acc['positions'] = account_update.positions
                account_updated = True
                break
        
        if not account_updated:
            # If account not found, add it
            data['accounts'].append(account_update.dict())
        
        # Save updated accounts
        with open('sandbox/config/synthetic_accounts.json', 'w') as f:
            json.dump(data, f, indent=2)
        
        # Update the sandbox service if it exists
        sandbox_service = getattr(app.state, 'sandbox_service', None)
        if sandbox_service and hasattr(sandbox_service, 'position_manager'):
            sandbox_service.position_manager.load_accounts('sandbox/config/synthetic_accounts.json')
        
        return {"success": True, "message": f"Account {account_update.account_id} updated successfully."}
    except Exception as e:
        logger.error(f"Error updating synthetic account: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update account: {str(e)}")

@app.post("/sandbox/trades/execute")
async def execute_sandbox_trade_endpoint(trade_request: TradeRequest, request_obj: Request, background_tasks: BackgroundTasks):
    """Execute a trade in the sandbox environment."""
    try:
        local_sandbox_service = getattr(request_obj.app.state, 'sandbox_service', None)
        local_ws_manager = getattr(request_obj.app.state, 'ws_manager', None)
        local_pricing_engine = getattr(request_obj.app.state, 'pricing_engine', None)
        local_data_feed_manager = getattr(request_obj.app.state, 'data_feed_manager', None)
        local_trade_executor = getattr(request_obj.app.state, 'trade_executor', None)

        # Validate service availability
        if not local_sandbox_service:
            raise HTTPException(status_code=503, detail="Sandbox service not available")
        if not local_trade_executor:
            raise HTTPException(status_code=503, detail="Trade executor not available")
        
        # Validate market data
        current_price = None
        if local_data_feed_manager and local_data_feed_manager.is_running:
            current_price = local_data_feed_manager.get_current_price()
        if not current_price and local_pricing_engine:
            current_price = local_pricing_engine.current_price
        
        if not current_price or current_price <= 0:
            raise HTTPException(status_code=503, detail="Market price not available")

        # Validate trade request
        if trade_request.quantity <= 0:
            raise HTTPException(status_code=400, detail="Invalid quantity")
        if trade_request.strike <= 0:
            raise HTTPException(status_code=400, detail="Invalid strike price")
        if trade_request.expiry_minutes not in config.AVAILABLE_EXPIRIES_MINUTES:
            raise HTTPException(status_code=400, detail=f"Invalid expiry. Available: {config.AVAILABLE_EXPIRIES_MINUTES}")

        # Create user account if it doesn't exist
        if trade_request.user_id not in local_trade_executor.user_accounts:
            local_trade_executor.create_user_account(trade_request.user_id)

        # Convert trade request to sandbox format
        sandbox_trade_data = {
            "user_id": trade_request.user_id,
            "symbol": f"BTC-{trade_request.option_type.upper()}",
            "quantity": trade_request.quantity,
            "side": trade_request.side.lower(),
            "strike": trade_request.strike,
            "expiry_minutes": trade_request.expiry_minutes,
            "option_type": trade_request.option_type.lower(),
            "current_price": current_price
        }

        # Execute trade in sandbox
        success, message, result = await local_sandbox_service.execute_sandbox_trade(sandbox_trade_data)
        
        if not success:
            logger.error(f"Sandbox trade execution failed: {message}")
            raise HTTPException(status_code=400, detail=message)

        # Notify connected clients if websocket manager is available
        if local_ws_manager:
            background_tasks.add_task(
                local_ws_manager.broadcast_safe,
                {
                    "type": "sandbox_trade_executed",
                    "data": {
                        "user_id": trade_request.user_id,
                        "symbol": sandbox_trade_data["symbol"],
                        "quantity": trade_request.quantity,
                        "side": trade_request.side,
                        "strike": trade_request.strike,
                        "result": result
                    }
                },
                user_id=trade_request.user_id
            )

        return {
            "status": "success",
            "trade_id": f"sandbox_{uuid.uuid4().hex[:8]}",
            "result": result
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in sandbox trade execution: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources when the application shuts down."""
    logger.info("Shutting down API components...")
    try:
        # Cancel background tasks
        if hasattr(app.state, 'position_updates_task'):
            app.state.position_updates_task.cancel()
            try:
                await app.state.position_updates_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"Error cancelling position updates task: {e}")

        # Stop sandbox service if it exists
        sandbox_service = getattr(app.state, 'sandbox_service', None)
        if sandbox_service:
            sandbox_service.stop()
            logger.info("Sandbox service stopped.")

        # Stop data feed manager if it exists
        data_feed_manager = getattr(app.state, 'data_feed_manager', None)
        if data_feed_manager:
            data_feed_manager.stop()
            logger.info("Data feed manager stopped.")

        # Close all WebSocket connections
        ws_manager = getattr(app.state, 'ws_manager', None)
        if ws_manager:
            for websocket in ws_manager.active_connections:
                try:
                    await websocket.close()
                except Exception as e:
                    logger.error(f"Error closing WebSocket connection: {e}")
            logger.info("All WebSocket connections closed.")

        logger.info("✅ API shutdown complete.")
    except Exception as e:
        logger.error(f"❌ API shutdown error: {e}", exc_info=True)
        raise

# +++ SIMPLE CHAT ENDPOINT WITH STOCK PROMPTS +++
@app.post("/chat")
async def chat_endpoint(chat_request: dict):
    """Simple HTTP chat endpoint with stock prompts for options education."""
    try:
        message = chat_request.get("message", "").lower().strip()
        
        # Check for stock prompt matches
        for prompt_id, prompt_data in STOCK_PROMPTS.items():
            if any(keyword in message for keyword in prompt_data["question"].lower().split()):
                return {
                    "type": "chat_response",
                    "data": {
                        "answer": prompt_data["answer"],
                        "question": prompt_data["question"],
                        "timestamp": time.time()
                    }
                }
        
        # Default response for unrecognized questions
        return {
            "type": "chat_response",
            "data": {
                "answer": "I can help explain options trading concepts. Try asking about: ATM/ITM/OTM, Greeks, implied volatility, time decay, or risk management strategies.",
                "available_topics": list(STOCK_PROMPTS.keys()),
                "timestamp": time.time()
            }
        }
        
    except Exception as chat_error:
        logger.error(f"Chat processing error: {chat_error}")
        return {
            "type": "chat_response",
            "data": {
                "answer": "Sorry, I'm having trouble processing your question right now.",
                "error": str(chat_error),
                "timestamp": time.time()
            }
        }

@app.get("/chat/prompts")
async def get_available_prompts():
    """Get list of available stock prompts."""
    return {
        "prompts": [
            {
                "id": prompt_id,
                "question": prompt_data["question"]
            }
            for prompt_id, prompt_data in STOCK_PROMPTS.items()
        ]
    }

# --- Sandbox Status Endpoint ---
@app.get("/sandbox-status", tags=["Sandbox"])
async def get_sandbox_status():
    """Endpoint to get the current status and analysis from the sandbox."""
    try:
        sandbox_service = getattr(app.state, 'sandbox_service', None)
        if sandbox_service:
            analysis = await sandbox_service.get_current_analysis()
            return analysis
        else:
            return {
                "status": "Sandbox not running or not initialized",
                "sandbox_exists": False
            }
    except Exception as e:
        logger.error(f"Error getting sandbox analysis: {e}", exc_info=True)
        return {
            "status": "Error retrieving sandbox analysis", 
            "error": str(e),
            "error_type": type(e).__name__
        }

# --- Main Execution Guard (if api.py is run directly) ---
if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting Uvicorn server directly from api.py for {config.PLATFORM_NAME} on {config.API_HOST}:{config.API_PORT}")
    uvicorn.run(
        "backend.api:app", # Ensure this points to the app object correctly
        host=config.API_HOST,
        port=config.API_PORT,
        log_level=config.LOG_LEVEL.lower(), 
        reload=config.DEMO_MODE 
    )
