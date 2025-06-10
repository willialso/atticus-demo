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

# --- CORE IMPORTS ---
from backend import config # Your main configuration file
from backend.advanced_pricing_engine import AdvancedPricingEngine
from backend.volatility_engine import AdvancedVolatilityEngine
from backend.alpha_signals import AlphaSignalGenerator
from backend.portfolio_hedger import PortfolioHedger
from backend.trade_executor import TradeExecutor, TradeOrder, OrderSide, UserAccount
from backend.data_feed_manager import DataFeedManager
from backend.utils import setup_logger # Your logging utility

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

# Setup Logger
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logger = setup_logger(__name__)

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

# --- FastAPI Application Setup ---
app = FastAPI(
    title=f"{config.PLATFORM_NAME} API",
    version=config.VERSION,
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
        await websocket.accept()
        async with self._lock:
            self.active_connections.append(websocket)
            if user_id: self.user_connections[user_id] = websocket
        logger.info(f"🔌 WebSocket connected (Total: {len(self.active_connections)}, Users: {len(self.user_connections)})")

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
                    pricing_engine_instance.update_market_data(price_val, volume_val)
                    _handle_price_update_sync.latest_price = price_val # Store on function object
                else:
                    logger.debug(f"Received invalid price_data in callback: {price_data}")
            else:
                logger.warning("Pricing engine not found on app.state, cannot handle price update.")
                _handle_price_update_sync.latest_price = getattr(price_data, 'price', 0.0) # Still try to store
        except Exception as e:
            logger.error(f"❌ Error in _handle_price_update_sync: {e}", exc_info=True)
            _handle_price_update_sync.latest_price = getattr(price_data, 'price', 0.0) # Attempt to store
    _handle_price_update_sync.latest_price = 0.0 # Initialize attribute
    return _handle_price_update_sync

# --- FastAPI Startup Event ---
@app.on_event("startup")
async def startup_event():
    logger.info(f"🚀 API Initializing {config.PLATFORM_NAME} v{config.VERSION} Components...")
    try:
        # Initialize and assign components to app.state
        app.state.vol_engine_global_instance = AdvancedVolatilityEngine()
        app.state.alpha_gen_global_instance = AlphaSignalGenerator()
        app.state.pricing_engine = AdvancedPricingEngine(
            volatility_engine=app.state.vol_engine_global_instance,
            alpha_signal_generator=app.state.alpha_gen_global_instance
        )

        if RL_HEDGER_AVAILABLE and getattr(config, 'USE_RL_HEDGER', False):
            try:
                app.state.hedger = RLHedger(pricing_engine=app.state.pricing_engine)
                logger.info("Using RL-enhanced hedger.")
            except Exception as e_rl:
                logger.warning(f"Failed to initialize RL hedger: {e_rl}. Falling back to PortfolioHedger.")
                app.state.hedger = PortfolioHedger(pricing_engine=app.state.pricing_engine)
        else:
            app.state.hedger = PortfolioHedger(pricing_engine=app.state.pricing_engine)

        app.state.trade_executor = TradeExecutor(
            pricing_engine=app.state.pricing_engine,
            hedger=app.state.hedger
        )
        
        app.state.data_feed_manager = DataFeedManager()
        price_update_callback = _handle_price_update_sync_factory(app) # Get callback with app context
        app.state.data_feed_manager.add_price_callback(price_update_callback)
        app.state.data_feed_manager.start()

        app.state.ws_manager = ws_manager_global_instance # Make ws_manager accessible via app.state

        # Pass app instance to background tasks if they need access to app.state
        asyncio.create_task(background_market_updates(app))
        asyncio.create_task(background_position_updates(app))
        
        logger.info(f"✅ API {config.PLATFORM_NAME} started successfully with all components on app.state.")
        api_startup_complete_event.set()
        logger.info("✅ API startup_complete_event has been set.")

    except Exception as e_startup:
        logger.error(f"❌ API Startup failed critically: {e_startup}", exc_info=True)
        api_startup_complete_event.set() # Also set event on failure
        raise RuntimeError(f"API Startup failed: {e_startup}")

# --- Background Tasks (now accept app instance) ---
async def background_market_updates(app_instance: FastAPI):
    last_broadcast_price = None; update_counter = 0
    loop_interval_seconds = 0.1 
    broadcast_check_loops = int(config.DATA_BROADCAST_INTERVAL_SECONDS / loop_interval_seconds if config.DATA_BROADCAST_INTERVAL_SECONDS >= loop_interval_seconds else 1)
    await asyncio.sleep(2) 
    logger.info("Background market updates task started.")
    
    price_update_callback_ref = _handle_price_update_sync_factory(app_instance) # Get ref to the latest_price attribute

    while True:
        try:
            current_price_for_broadcast = 0.0
            local_pricing_engine = getattr(app_instance.state, 'pricing_engine', None)
            local_ws_manager = getattr(app_instance.state, 'ws_manager', None)

            if local_pricing_engine and hasattr(local_pricing_engine, 'current_price') and local_pricing_engine.current_price > 0:
                current_price_for_broadcast = local_pricing_engine.current_price
            elif hasattr(price_update_callback_ref, 'latest_price'): 
                current_price_for_broadcast = price_update_callback_ref.latest_price

            if current_price_for_broadcast > 0 and local_ws_manager:
                should_broadcast_flag = False; price_diff = 0.0
                price_change_threshold_val = getattr(config, 'PRICE_CHANGE_THRESHOLD_FOR_BROADCAST', 0.0001)
                
                if last_broadcast_price is None or \
                   (last_broadcast_price > 0 and abs(current_price_for_broadcast - last_broadcast_price) / last_broadcast_price > price_change_threshold_val):
                    should_broadcast_flag = True
                
                if last_broadcast_price is not None:
                    price_diff = current_price_for_broadcast - last_broadcast_price
                
                update_counter = (update_counter + 1) % broadcast_check_loops
                if update_counter == 0: 
                    should_broadcast_flag = True

                if should_broadcast_flag:
                    await local_ws_manager.broadcast_safe({
                        "type": "price_update",
                        "data": {"price": current_price_for_broadcast, "change": price_diff, "timestamp": time.time()}
                    })
                    last_broadcast_price = current_price_for_broadcast
        except Exception as e_bg_market:
            logger.error(f"❌ Background market update task error: {e_bg_market}", exc_info=True)
        await asyncio.sleep(loop_interval_seconds)

async def background_position_updates(app_instance: FastAPI):
    await asyncio.sleep(3)
    logger.info("Background position updates task started.")
    
    price_update_callback_ref = _handle_price_update_sync_factory(app_instance)

    while True:
        try:
            local_trade_executor = getattr(app_instance.state, 'trade_executor', None)
            local_pricing_engine = getattr(app_instance.state, 'pricing_engine', None)
            local_ws_manager = getattr(app_instance.state, 'ws_manager', None)

            current_btc_price_for_marks = 0.0
            if local_pricing_engine and hasattr(local_pricing_engine, 'current_price') and local_pricing_engine.current_price > 0:
                current_btc_price_for_marks = local_pricing_engine.current_price
            elif hasattr(price_update_callback_ref, 'latest_price'): 
                current_btc_price_for_marks = price_update_callback_ref.latest_price

            if local_trade_executor and current_btc_price_for_marks > 0:
                local_trade_executor.update_position_marks(current_btc_price_for_marks) 
                settled_list = local_trade_executor.check_and_settle_expired_options()
                if settled_list and local_ws_manager:
                    for settled_pos in settled_list:
                        await local_ws_manager.broadcast_safe({
                            "type": "position_settled",
                            "data": {"position_id": settled_pos.position_id, "final_pnl": settled_pos.unrealized_pnl}
                        }, user_id=settled_pos.user_id)
        except Exception as e_bg_pos:
            logger.error(f"❌ Background position update task error: {e_bg_pos}", exc_info=True)
        await asyncio.sleep(1.0) 

# --- API Endpoints (now use app.state for components) ---
@app.get("/")
async def health_check_endpoint(request: Request):
    current_price_val = 0.0
    local_pricing_engine = getattr(request.app.state, 'pricing_engine', None)
    price_update_callback_ref = _handle_price_update_sync_factory(request.app)

    if local_pricing_engine and hasattr(local_pricing_engine, 'current_price') and local_pricing_engine.current_price > 0:
        current_price_val = local_pricing_engine.current_price
    elif hasattr(price_update_callback_ref, 'latest_price'):
        current_price_val = price_update_callback_ref.latest_price
        
    return {"name": config.PLATFORM_NAME, "version": config.VERSION, "status": "operational",
            "timestamp": time.time(), "current_btc_price_api": current_price_val}

@app.post("/blackscholes/calculate")
async def calculate_black_scholes_basic_endpoint(request_data: BlackScholesRequest): # Changed param name
    r_val = request_data.risk_free_rate if request_data.risk_free_rate is not None else config.RISK_FREE_RATE
    sigma_val = request_data.volatility if request_data.volatility is not None else config.DEFAULT_VOLATILITY_FOR_BASIC_BS
    try:
        premium_calc, greeks_calc = AdvancedPricingEngine.black_scholes_with_greeks(
            S=request_data.current_price, K=request_data.strike_price, T=request_data.time_to_expiry_years,
            r=r_val, sigma=sigma_val, option_type=request_data.option_type
        )
        inputs_echo = request_data.dict()
        inputs_echo['risk_free_rate'] = r_val
        inputs_echo['volatility'] = sigma_val
        return {"premium_usd_per_btc": premium_calc, "greeks": greeks_calc, "inputs_used": inputs_echo}
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

# +++ FIXED: WebSocket endpoint - removed 'request: Request' parameter +++
@app.websocket("/ws")
async def websocket_connection_endpoint(websocket: WebSocket, user_id: Optional[str] = None):
    # Get components from app.state directly via websocket.app.state (not request.app.state)
    local_ws_manager = getattr(websocket.app.state, 'ws_manager', None)
    local_pricing_engine = getattr(websocket.app.state, 'pricing_engine', None)
    price_update_callback_ref = _handle_price_update_sync_factory(websocket.app)

    if not local_ws_manager:
        logger.error("WebSocket connection attempt but ws_manager not found on app.state.")
        await websocket.accept()
        await websocket.close(code=1011, reason="WebSocket manager not available")
        return

    connection_id = f"{user_id}_" if user_id else ""
    connection_id += f"{websocket.client.host}_{websocket.client.port}"
    await local_ws_manager.connect(websocket, user_id)
    
    try:
        current_price_val_ws = 0.0
        if local_pricing_engine and hasattr(local_pricing_engine, 'current_price') and local_pricing_engine.current_price > 0:
            current_price_val_ws = local_pricing_engine.current_price
        elif hasattr(price_update_callback_ref, 'latest_price'):
            current_price_val_ws = price_update_callback_ref.latest_price
        
        await websocket.send_text(json.dumps({
            "type": "connected", 
            "data": {
                "message": f"Connected to {config.PLATFORM_NAME}", 
                "current_price": current_price_val_ws, 
                "timestamp": time.time()
            }
        }))
        
        while True:
            try:
                data_received = await asyncio.wait_for(websocket.receive_text(), timeout=config.WEBSOCKET_TIMEOUT_SECONDS)
                message_obj = json.loads(data_received)
                if message_obj.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong", "timestamp": time.time()}))
            except asyncio.TimeoutError:
                await websocket.send_text(json.dumps({"type": "keepalive", "timestamp": time.time()}))
            except WebSocketDisconnect:
                logger.info(f"WebSocket {connection_id} disconnected by client.")
                break
            except json.JSONDecodeError:
                logger.warning(f"WebSocket {connection_id} received invalid JSON.")
            except Exception as e_ws_loop:
                logger.warning(f"WebSocket error for {connection_id} during receive/process: {e_ws_loop}")
                break
    except Exception as e_ws_conn:
        logger.error(f"❌ WebSocket connection error for {connection_id}: {e_ws_conn}", exc_info=True)
    finally:
        logger.info(f"Closing WebSocket connection for: {connection_id}")
        if local_ws_manager:
            await local_ws_manager.disconnect(websocket, user_id)
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

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
