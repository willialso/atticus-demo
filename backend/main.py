# backend/main.py

import asyncio
import sys
import signal
from typing import Optional, List, Dict, Any
from fastapi import FastAPI
import uvicorn
import os

# Add project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from backend import config
from backend.data_feed_manager import DataFeedManager
from backend.regime_detector import MarketRegimeDetector
from backend.api import app as fastapi_app_instance
from backend.api import api_startup_complete_event
from backend.utils import setup_logger

# --- CORRECTED SANDBOX IMPORT (FOR SIBLING DIRECTORIES) ---
from sandbox.api.websocket_extension import SandboxService

# Type hint imports
from backend.advanced_pricing_engine import AdvancedPricingEngine
from backend.portfolio_hedger import PortfolioHedger
from backend.trade_executor import TradeExecutor

try:
    from backend.rl_hedger import RLHedger
    RL_HEDGER_AVAILABLE = True
except ImportError:
    RL_HEDGER_AVAILABLE = False

try:
    from backend.ml_volatility_engine import MLVolatilityEngine
    ML_VOLATILITY_AVAILABLE = True
except ImportError:
    ML_VOLATILITY_AVAILABLE = False

if config.SENTIMENT_ANALYSIS_ENABLED:
    try:
        from backend.sentiment_analyzer import SentimentAnalyzer
        SENTIMENT_ANALYZER_AVAILABLE = True
    except ImportError:
        SENTIMENT_ANALYZER_AVAILABLE = False
else:
    SENTIMENT_ANALYZER_AVAILABLE = False

logger = setup_logger(__name__)

# --- FIXED: Enhanced DataHub class with both async and sync updates ---
class DataHub:
    """Enhanced DataHub implementation for reliable sandbox price integration."""
    def __init__(self):
        self._data: Dict[str, Any] = {}
        self._lock = asyncio.Lock()
        self._latest_price = 0.0  # Cache latest price for immediate access
        logger.info("DataHub initialized for sandbox integration.")

    async def update_data(self, new_data: Dict[str, Any]):
        """Update data in thread-safe manner with price caching."""
        try:
            async with self._lock:
                self._data.update(new_data)
                # Cache the latest price for immediate access
                if "platform_btc_price" in new_data:
                    self._latest_price = new_data["platform_btc_price"]
                    logger.debug(f"DataHub async price updated: ${self._latest_price:,.2f}")
        except Exception as e:
            logger.error(f"Error in DataHub async update: {e}")
            # Fallback to direct update
            self._data.update(new_data)
            if "platform_btc_price" in new_data:
                self._latest_price = new_data["platform_btc_price"]

    def update_data_sync(self, new_data: Dict[str, Any]):
        """CRITICAL FIX: Synchronous update for immediate price updates."""
        self._data.update(new_data)
        if "platform_btc_price" in new_data:
            self._latest_price = new_data["platform_btc_price"]
            logger.info(f"✅ DataHub sync price updated: ${self._latest_price:,.2f}")

    async def get_data(self) -> Dict[str, Any]:
        """Get data in thread-safe manner."""
        try:
            async with self._lock:
                return self._data.copy()
        except Exception:
            return self._data.copy()

    def get_current_price_sync(self) -> float:
        """Get current price synchronously for hedging calculations."""
        return self._latest_price

# Create global DataHub instance
data_hub = DataHub()

class AtticusBackend:
    def __init__(self, app_instance: FastAPI):
        self.app = app_instance
        self.data_feed_manager: Optional[DataFeedManager] = None
        self.pricing_engine: Optional[AdvancedPricingEngine] = None
        self.hedger: Optional[PortfolioHedger] = None
        self.trade_executor: Optional[TradeExecutor] = None
        self.sentiment_analyzer: Optional[SentimentAnalyzer] = None
        self.regime_detector: Optional[MarketRegimeDetector] = None
        self.is_running = False
        # --- UPDATE: AtticusBackend now owns the sandbox service ---
        self.sandbox_service: Optional[SandboxService] = None

    async def initialize_from_api_components(self):
        logger.info("AtticusBackend retrieving components from app.state...")
        self.data_feed_manager = getattr(self.app.state, 'data_feed_manager', None)
        self.pricing_engine = getattr(self.app.state, 'pricing_engine', None)
        self.hedger = getattr(self.app.state, 'hedger', None)
        self.trade_executor = getattr(self.app.state, 'trade_executor', None)

        if not all([self.data_feed_manager, self.pricing_engine, self.hedger, self.trade_executor]):
            missing = []
            if not self.data_feed_manager: missing.append("data_feed_manager")
            if not self.pricing_engine: missing.append("pricing_engine")
            if not self.hedger: missing.append("hedger")
            if not self.trade_executor: missing.append("trade_executor")
            logger.error(f"Critical API components not found on app.state. Missing: {', '.join(missing)}")
            raise RuntimeError(f"API components ({', '.join(missing)}) not found on app.state after API startup signal.")

        # --- FIXED: Initialize the sandbox with BOTH data_hub and pricing_engine ---
        try:
            logger.info("Initializing SandboxService inside AtticusBackend...")
            # CRITICAL FIX: Pass both required arguments
            self.sandbox_service = SandboxService(data_hub=data_hub, pricing_engine=self.pricing_engine)
            # Hook sandbox into the live data feed via multiple callbacks
            self.data_feed_manager.add_price_callback(self._sandbox_price_callback)
            logger.info("SandboxService initialized and hooked into data feed successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize SandboxService: {e}", exc_info=True)
            self.sandbox_service = None # Ensure it's None on failure

        if config.SENTIMENT_ANALYSIS_ENABLED and SENTIMENT_ANALYZER_AVAILABLE:
            try:
                self.sentiment_analyzer = SentimentAnalyzer()
                logger.info("Sentiment analyzer initialized by AtticusBackend.")
            except Exception as e:
                logger.warning(f"Failed to initialize sentiment analyzer in AtticusBackend: {e}")
        else:
            logger.info("Sentiment analysis disabled or unavailable for AtticusBackend.")

        if getattr(config, 'REGIME_DETECTION_ENABLED', False):
            try:
                self.regime_detector = MarketRegimeDetector()
                logger.info("Regime detector initialized by AtticusBackend.")
            except Exception as e:
                logger.warning(f"Failed to initialize regime detector in AtticusBackend: {e}")
        else:
            logger.info("Regime detection disabled for AtticusBackend.")
        
        if self.data_feed_manager:
            self.data_feed_manager.add_price_callback(self._on_price_update)
            logger.info("AtticusBackend added its own price update callback.")
        
        logger.info("AtticusBackend synchronized with API components successfully.")

    def _sandbox_price_callback(self, price_data):
        """CRITICAL FIX: Synchronous callback to reliably feed price data to sandbox."""
        try:
            current_price = getattr(price_data, 'price', None)
            if current_price and current_price > 0:
                # CRITICAL FIX: Use synchronous update to ensure immediate execution
                data_hub.update_data_sync({
                    "platform_btc_price": current_price,
                    "timestamp": getattr(price_data, 'time', None),
                    "implied_volatility": getattr(self.pricing_engine, 'current_volatility', 0.25) if self.pricing_engine else 0.25
                })
                
                # CRITICAL FIX: Also directly update the sandbox with current price
                if self.sandbox_service and hasattr(self.sandbox_service, 'update_current_price'):
                    self.sandbox_service.update_current_price(current_price)
                
                logger.debug(f"✅ Sandbox price callback executed: ${current_price:,.2f}")
            else:
                logger.warning(f"Invalid price data received: {current_price}")
                
        except Exception as e:
            logger.error(f"Error in sandbox price callback: {e}", exc_info=True)

    def _on_price_update(self, price_data):
        try:
            current_price = getattr(price_data, 'price', None)
            current_volume = getattr(price_data, 'volume', None)
            if current_price is None: 
                return

            if self.regime_detector:
                try: 
                    self.regime_detector.update_data(current_price, current_volume)
                except Exception as e: 
                    logger.debug(f"Regime detector update error: {e}")
            
            if self.sentiment_analyzer:
                try:
                    if hasattr(self.sentiment_analyzer, 'update_tick'): 
                        self.sentiment_analyzer.update_tick(current_price, current_volume)
                    elif hasattr(self.sentiment_analyzer, 'update_price'): 
                        self.sentiment_analyzer.update_price(current_price, current_volume)
                except Exception as e: 
                    logger.debug(f"Sentiment analyzer update error: {e}")

            if self.hedger and getattr(config, 'HEDGING_ENABLED', False):
                try:
                    if hasattr(self.hedger, 'should_rehedge') and self.hedger.should_rehedge(current_price):
                        if hasattr(self.hedger, 'execute_delta_hedge'): 
                            self.hedger.execute_delta_hedge(current_price)
                except Exception as e: 
                    logger.debug(f"Hedging update error in AtticusBackend: {e}")
        except Exception as e:
            logger.debug(f"Error processing price update in AtticusBackend: {e}")

    async def start(self):
        """Start AtticusBackend and its managed services like the sandbox."""
        logger.info("Starting Atticus Backend (post-API init)...")
        try:
            await self.initialize_from_api_components()
            
            # --- UPDATE: Start the sandbox service if it was initialized ---
            if self.sandbox_service:
                self.sandbox_service.start()
                # CRITICAL FIX: Initialize sandbox with current price from pricing engine
                if self.pricing_engine and self.pricing_engine.current_price > 0:
                    initial_price = self.pricing_engine.current_price
                    # Use synchronous update to ensure immediate availability
                    data_hub.update_data_sync({
                        "platform_btc_price": initial_price,
                        "timestamp": None,
                        "implied_volatility": getattr(self.pricing_engine, 'current_volatility', 0.25)
                    })
                    if hasattr(self.sandbox_service, 'update_current_price'):
                        self.sandbox_service.update_current_price(initial_price)
                    logger.info(f"✅ SandboxService initialized with current price: ${initial_price:,.2f}")
                else:
                    logger.info("SandboxService started successfully.")

            self.is_running = True
            logger.info("Atticus Backend (main logic) entering background tasks loop...")
            await self._background_tasks()
        except Exception as e:
            logger.error(f"Failed to start or run Atticus Backend main logic: {e}", exc_info=True)
            self.is_running = False
            raise

    async def stop(self):
        """Stop AtticusBackend and its managed services."""
        if not self.is_running:
            return
        logger.info("Stopping Atticus Backend (main logic)...")
        self.is_running = False
        
        # --- UPDATE: Stop the sandbox service if it's running ---
        if self.sandbox_service and hasattr(self.sandbox_service, 'is_running') and self.sandbox_service.is_running:
            self.sandbox_service.stop()
            logger.info("SandboxService stopped.")

        await asyncio.sleep(0.1)
        if self.data_feed_manager and hasattr(self.data_feed_manager, 'stop') and callable(getattr(self.data_feed_manager, 'stop')):
            if self.data_feed_manager.is_running:
                self.data_feed_manager.stop()
                logger.info("DataFeedManager stopped by AtticusBackend during its shutdown.")
        if self.hedger and hasattr(self.hedger, 'save_rl_model') and callable(getattr(self.hedger, 'save_rl_model')):
            try: 
                self.hedger.save_rl_model()
                logger.info("RL hedger model saved (if applicable).")
            except Exception as e: 
                logger.warning(f"Failed to save RL model: {e}")
        logger.info("Atticus Backend (main logic) stopped.")

    async def _background_tasks(self):
        """Main background tasks loop - runs until is_running becomes False."""
        logger.info("AtticusBackend: Background tasks started.")
        while self.is_running:
            try:
                current_btc_price_for_marks = 0
                if self.pricing_engine and self.pricing_engine.current_price > 0:
                    current_btc_price_for_marks = self.pricing_engine.current_price
                if self.trade_executor and current_btc_price_for_marks > 0:
                    self.trade_executor.update_position_marks(current_btc_price_for_marks)
                    settled_positions = self.trade_executor.check_and_settle_expired_options()
                if self.pricing_engine and hasattr(self.pricing_engine, 'vol_engine'):
                    vol_engine_ref = self.pricing_engine.vol_engine
                    if (isinstance(vol_engine_ref, MLVolatilityEngine) and 
                        ML_VOLATILITY_AVAILABLE and
                        hasattr(vol_engine_ref, 'feature_history') and
                        len(vol_engine_ref.feature_history) > 0 and 
                        len(vol_engine_ref.feature_history) % getattr(config, 'ML_VOL_TRAINING_INTERVAL', 500) == 0):
                        try: 
                            vol_engine_ref.train_models()
                            logger.debug("ML vol models trained.")
                        except Exception as e: 
                            logger.debug(f"ML model training error: {e}")
                if self.regime_detector and hasattr(self.regime_detector, 'return_history') and \
                   len(self.regime_detector.return_history) > 0 and \
                   len(self.regime_detector.return_history) % getattr(config, 'REGIME_TRAINING_INTERVAL', 1000) == 0:
                    try:
                        self.regime_detector.train_hmm_model()
                        self.regime_detector.train_gmm_model()
                        self.regime_detector.train_kmeans_model()
                        logger.debug("Regime models trained.")
                    except Exception as e: 
                        logger.debug(f"Regime model training error: {e}")
                if self.sentiment_analyzer and hasattr(self.sentiment_analyzer, 'generate_sentiment_signal'):
                    try: 
                        self.sentiment_analyzer.generate_sentiment_signal()
                        logger.debug("Sentiment signal generated.")
                    except Exception as e: 
                        logger.debug(f"Sentiment analysis error: {e}")
                await asyncio.sleep(getattr(config, 'ATTICUS_BACKGROUND_TASK_INTERVAL', 30))
            except asyncio.CancelledError:
                logger.info("AtticusBackend background task was cancelled.")
                break
            except Exception as e:
                logger.error(f"AtticusBackend background task error: {e}", exc_info=True)
                await asyncio.sleep(60)
        logger.info("AtticusBackend: Background tasks finished.")

# Global reference for signal handler and API endpoint
backend_instance_for_shutdown: Optional[AtticusBackend] = None

def signal_handler_main_py(signum, frame):
    """Signal handler for graceful shutdown."""
    global backend_instance_for_shutdown
    logger.info(f"Main.py: Received signal {signum}, initiating AtticusBackend graceful shutdown...")
    logger.info("Main.py signal handler: backend stop will be managed by main() finally block.")

# --- IMPROVED: Enhanced sandbox status endpoint with proper error handling ---
@fastapi_app_instance.get("/sandbox-status", tags=["Sandbox"])
async def get_sandbox_status():
    """Endpoint to get the current status and analysis from the sandbox with improved error handling."""
    try:
        if backend_instance_for_shutdown and backend_instance_for_shutdown.sandbox_service:
            # Try to get the analysis - this might be throwing an exception
            logger.debug("Attempting to get sandbox analysis...")
            analysis = await backend_instance_for_shutdown.sandbox_service.get_current_analysis()
            logger.debug("Successfully retrieved sandbox analysis")
            return analysis
        else:
            logger.warning("Sandbox status requested but sandbox service not available")
            return {
                "status": "Sandbox not running or not initialized",
                "backend_exists": backend_instance_for_shutdown is not None,
                "sandbox_exists": (backend_instance_for_shutdown.sandbox_service is not None) if backend_instance_for_shutdown else False
            }
    except Exception as e:
        logger.error(f"Error getting sandbox analysis: {e}", exc_info=True)
        return {
            "status": "Error retrieving sandbox analysis", 
            "error": str(e),
            "error_type": type(e).__name__,
            "sandbox_running": True  # We know from debug that it's running
        }

# --- ADDED: Debug endpoint to diagnose sandbox status issues ---
@fastapi_app_instance.get("/debug-backend", tags=["Debug"])
async def debug_backend_status():
    """Debug endpoint to check backend and sandbox status."""
    global backend_instance_for_shutdown
    
    debug_info = {
        "backend_instance_exists": backend_instance_for_shutdown is not None,
        "backend_is_running": False,
        "sandbox_service_exists": False,
        "sandbox_is_running": False,
        "sandbox_type": "None",
        "sandbox_has_get_current_analysis": False,
        "current_demo_price": 0.0,
        "datahub_price": 0.0
    }
    
    if backend_instance_for_shutdown:
        debug_info["backend_is_running"] = getattr(backend_instance_for_shutdown, 'is_running', False)
        
        # Get current price from demo
        if backend_instance_for_shutdown.pricing_engine:
            debug_info["current_demo_price"] = getattr(backend_instance_for_shutdown.pricing_engine, 'current_price', 0.0)
        
        # Get price from DataHub
        debug_info["datahub_price"] = data_hub.get_current_price_sync()
        
        if hasattr(backend_instance_for_shutdown, 'sandbox_service'):
            sandbox_service = backend_instance_for_shutdown.sandbox_service
            debug_info["sandbox_service_exists"] = sandbox_service is not None
            debug_info["sandbox_type"] = str(type(sandbox_service))
            
            if sandbox_service:
                debug_info["sandbox_is_running"] = getattr(sandbox_service, 'is_running', False)
                debug_info["sandbox_has_get_current_analysis"] = hasattr(sandbox_service, 'get_current_analysis')
    
    return debug_info

# --- ADDED: Test endpoint to manually trigger price updates ---
@fastapi_app_instance.get("/test-sandbox-price", tags=["Debug"])
async def test_sandbox_price():
    """Test endpoint to manually trigger a price update and verify the flow."""
    try:
        if backend_instance_for_shutdown and backend_instance_for_shutdown.pricing_engine:
            current_price = backend_instance_for_shutdown.pricing_engine.current_price
            if current_price > 0:
                # Manually trigger the sandbox price callback
                class MockPriceData:
                    def __init__(self, price):
                        self.price = price
                        self.time = None
                
                mock_data = MockPriceData(current_price)
                backend_instance_for_shutdown._sandbox_price_callback(mock_data)
                
                return {
                    "test_triggered": True,
                    "price_sent": current_price,
                    "datahub_price_after": data_hub.get_current_price_sync(),
                    "success": data_hub.get_current_price_sync() > 0
                }
            else:
                return {"error": "No current price available from demo"}
        else:
            return {"error": "Backend or pricing engine not available"}
    except Exception as e:
        return {"error": str(e)}

# --- CRITICAL ADDITION: Comprehensive hedging flow debug endpoint ---
@fastapi_app_instance.get("/debug-hedging-flow", tags=["Debug"])
async def debug_hedging_flow():
    """CRITICAL: Trace the complete hedging execution flow step by step to identify exactly where hedging_plan generation fails."""
    try:
        if not (backend_instance_for_shutdown and backend_instance_for_shutdown.sandbox_service):
            return {"error": "Sandbox not available"}
        
        current_price = data_hub.get_current_price_sync()
        analysis = await backend_instance_for_shutdown.sandbox_service.get_current_analysis()
        portfolio_summary = analysis.get("portfolio_summary", {})
        
        # Test data
        market_data = {"btc_price": current_price, "volatility": 0.25}
        
        debug_info = {
            "step1_data_preparation": {
                "market_data": market_data,
                "portfolio_summary": portfolio_summary,
                "net_position": portfolio_summary.get("net_position", 0),
                "position_check": portfolio_summary.get("net_position", 0) > 0.1
            }
        }
        
        # Step 2: Test strategy factory
        try:
            strategy_factory = backend_instance_for_shutdown.sandbox_service.hedging_engine.strategy_factory
            debug_info["step2_strategy_factory"] = {
                "factory_exists": strategy_factory is not None,
                "pricing_engine_exists": strategy_factory.pricing_engine is not None if strategy_factory else False,
                "strategies_registered": len(strategy_factory._strategies) if strategy_factory else 0
            }
        except Exception as e:
            debug_info["step2_strategy_factory"] = {"error": str(e)}
        
        # Step 3: Test strategy import
        try:
            from sandbox.hedging.algorithms.protective_strategies import ProtectivePutStrategy, ProtectiveCallStrategy
            debug_info["step3_strategy_import"] = {"success": True, "both_strategies_imported": True}
        except Exception as e:
            debug_info["step3_strategy_import"] = {"error": str(e)}
            return debug_info
        
        # Step 4: Test strategy instantiation
        try:
            put_strategy = ProtectivePutStrategy(backend_instance_for_shutdown.pricing_engine)
            call_strategy = ProtectiveCallStrategy(backend_instance_for_shutdown.pricing_engine)
            debug_info["step4_strategy_creation"] = {
                "put_strategy_created": True,
                "call_strategy_created": True,
                "put_has_pricing_engine": put_strategy.pricing_engine is not None,
                "call_has_pricing_engine": call_strategy.pricing_engine is not None
            }
        except Exception as e:
            debug_info["step4_strategy_creation"] = {"error": str(e)}
            return debug_info
        
        # Step 5: Test individual strategy execution
        try:
            put_result = put_strategy.analyze(market_data, portfolio_summary)
            call_result = call_strategy.analyze(market_data, portfolio_summary)
            debug_info["step5_individual_strategy_execution"] = {
                "put_strategy_result": put_result.__dict__ if put_result else None,
                "call_strategy_result": call_result.__dict__ if call_result else None,
                "put_triggered": put_result is not None,
                "call_triggered": call_result is not None
            }
        except Exception as e:
            debug_info["step5_individual_strategy_execution"] = {"error": str(e), "traceback": str(e.__traceback__)}
        
        # Step 6: Test config access
        try:
            from sandbox.config.sandbox_config import SANDBOX_CONFIG
            debug_info["step6_config_test"] = {
                "config_imported": True,
                "default_expiry_hours": SANDBOX_CONFIG.DEFAULT_EXPIRY_HOURS,
                "default_strike_offsets": SANDBOX_CONFIG.DEFAULT_STRIKE_OFFSETS,
                "atm_offset": SANDBOX_CONFIG.DEFAULT_STRIKE_OFFSETS.get("ATM", "MISSING")
            }
        except Exception as e:
            debug_info["step6_config_test"] = {"error": str(e)}
        
        # Step 7: Test option pricing
        try:
            strike = current_price * (1 + SANDBOX_CONFIG.DEFAULT_STRIKE_OFFSETS["ATM"])
            expiry_hours = SANDBOX_CONFIG.DEFAULT_EXPIRY_HOURS[1]
            
            option_price = put_strategy._get_option_price(current_price, strike, expiry_hours, 0.25, 'put')
            debug_info["step7_option_pricing"] = {
                "current_price": current_price,
                "strike": strike,
                "expiry_hours": expiry_hours,
                "option_price": option_price,
                "pricing_successful": option_price > 0
            }
        except Exception as e:
            debug_info["step7_option_pricing"] = {"error": str(e)}
        
        # Step 8: Test hedging engine run_all_strategies
        try:
            recommended_strategies = strategy_factory.run_all_strategies(market_data, portfolio_summary)
            debug_info["step8_run_all_strategies"] = {
                "success": True,
                "strategies_count": len(recommended_strategies),
                "strategies": [s.__dict__ for s in recommended_strategies] if recommended_strategies else []
            }
        except Exception as e:
            debug_info["step8_run_all_strategies"] = {"error": str(e), "traceback": str(e.__traceback__)}
        
        # Step 9: Test complete hedging engine flow
        try:
            hedging_plan = backend_instance_for_shutdown.sandbox_service.hedging_engine.devise_hedging_plan(market_data, portfolio_summary)
            debug_info["step9_complete_hedging_flow"] = {
                "hedging_plan_exists": hedging_plan is not None,
                "hedging_plan": hedging_plan.__dict__ if hedging_plan else None
            }
        except Exception as e:
            debug_info["step9_complete_hedging_flow"] = {"error": str(e)}
        
        return debug_info
        
    except Exception as e:
        return {"error": str(e), "error_type": type(e).__name__}

@fastapi_app_instance.get("/", include_in_schema=False)
async def read_root():
    return {"message": "Welcome to Atticus v2.2"}

async def main():
    """Main function runs the server and the backend logic concurrently."""
    global backend_instance_for_shutdown
    signal.signal(signal.SIGINT, signal_handler_main_py)
    signal.signal(signal.SIGTERM, signal_handler_main_py)
    os.makedirs("logs", exist_ok=True)
    
    backend = AtticusBackend(app_instance=fastapi_app_instance)
    backend_instance_for_shutdown = backend 

    uvicorn_config = uvicorn.Config("backend.api:app", host=config.API_HOST, port=config.API_PORT, reload=config.DEMO_MODE, log_level=config.LOG_LEVEL.lower())
    server = uvicorn.Server(uvicorn_config)

    async def start_atticus_backend_logic_wrapper(backend_to_start):
        """Wrapper waits for API startup before starting the main logic."""
        logger.info("AtticusBackend logic waiting for API startup to complete...")
        try:
            await asyncio.wait_for(api_startup_complete_event.wait(), timeout=config.API_STARTUP_TIMEOUT)
            logger.info("API startup complete event received, starting main logic.")
            await backend_to_start.start()
        except asyncio.TimeoutError:
            logger.error(f"Timeout waiting for API startup complete event after {config.API_STARTUP_TIMEOUT}s. AtticusBackend logic will not start.")
        except RuntimeError as e:
             logger.error(f"RuntimeError during AtticusBackend startup: {e}. AtticusBackend logic will not start.")
        except Exception as e:
            logger.error(f"Unexpected error starting AtticusBackend logic: {e}", exc_info=True)
    
    api_server_task = asyncio.create_task(server.serve())
    atticus_logic_task = asyncio.create_task(start_atticus_backend_logic_wrapper(backend))

    try:
        done, pending = await asyncio.wait({api_server_task, atticus_logic_task}, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            task_name = task.get_name() if hasattr(task, 'get_name') else "Unknown Task"
            if task.exception():
                logger.error(f"Task '{task_name}' completed with an error: {task.exception()}", exc_info=task.exception())
            else:
                logger.info(f"Task '{task_name}' completed normally.")
        for task in pending:
            task_name = task.get_name() if hasattr(task, 'get_name') else "Unknown Task"
            logger.info(f"Cancelling pending task: '{task_name}'")
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    logger.info(f"Task '{task_name}' was successfully cancelled.")
                except Exception as e_cancel:
                    logger.error(f"Exception while awaiting cancellation of task '{task_name}': {e_cancel}")
    except KeyboardInterrupt:
        logger.info("Shutdown requested by user (main.py via KeyboardInterrupt).")
    except Exception as e:
        logger.error(f"Application error in main.py's concurrent execution: {e}", exc_info=True)
    finally:
        logger.info("Main.py initiating shutdown sequence...")
        if backend_instance_for_shutdown and backend_instance_for_shutdown.is_running:
            await backend_instance_for_shutdown.stop()
        else:
            logger.info("AtticusBackend was not running or already stopped/failed to start.")
        if not api_server_task.done():
            logger.info("Attempting to trigger Uvicorn server shutdown...")
            if hasattr(server, 'handle_exit') and callable(getattr(server, 'handle_exit')):
                 server.handle_exit(sig=signal.SIGINT, frame=None)
            else:
                api_server_task.cancel()
            try:
                await api_server_task
            except asyncio.CancelledError:
                logger.info("Uvicorn server task was cancelled during shutdown sequence.")
            except Exception as e_server_shutdown:
                logger.error(f"Error during explicit Uvicorn server shutdown: {e_server_shutdown}")
        else:
            logger.info("Uvicorn server task already completed.")
        logger.info("Main.py shutdown sequence complete.")

if __name__ == "__main__":
    """
    This ensures the main() function with all the concurrent task logic actually runs.
    """
    try:
        asyncio.run(main())
    except Exception as e_outer_main:
        print(f"CRITICAL UNHANDLED ERROR in main: {e_outer_main}")
