# backend/main.py

import asyncio
import sys
import signal
from typing import Optional
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
        """Start AtticusBackend and run its main background tasks loop."""
        logger.info("Starting Atticus Backend (post-API init)...")
        try:
            await self.initialize_from_api_components()
            
            self.is_running = True
            logger.info("Atticus Backend (main logic) components initialized, entering background tasks loop...")
            
            # +++ FIXED: Directly await the main background tasks loop +++
            # This makes AtticusBackend.start() a long-running method that only
            # completes when the background tasks loop exits (on graceful stop)
            await self._background_tasks()
            # +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
            
            logger.info("Atticus Backend (main logic) has completed its run.")

        except Exception as e:
            logger.error(f"Failed to start or run Atticus Backend main logic: {e}", exc_info=True)
            self.is_running = False
            raise

    async def stop(self):
        """Stop AtticusBackend by setting is_running to False and cleaning up resources."""
        if not self.is_running:
            logger.info("Atticus Backend (main logic) already stopped or was not fully started.")
            return

        logger.info("Stopping Atticus Backend (main logic)...")
        self.is_running = False  # This will cause _background_tasks loop to exit

        # Give the background tasks loop a moment to exit gracefully
        await asyncio.sleep(0.1)

        # Clean up data feed manager if needed
        if self.data_feed_manager and hasattr(self.data_feed_manager, 'stop') and callable(getattr(self.data_feed_manager, 'stop')):
            # +++ FIXED: Access is_running as attribute, not method +++
            if self.data_feed_manager.is_running:  # No parentheses
                self.data_feed_manager.stop()
                logger.info("DataFeedManager stopped by AtticusBackend during its shutdown.")
            # ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

        # Save RL model if applicable
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
                # Update position marks
                current_btc_price_for_marks = 0
                if self.pricing_engine and self.pricing_engine.current_price > 0:
                    current_btc_price_for_marks = self.pricing_engine.current_price
                
                if self.trade_executor and current_btc_price_for_marks > 0:
                    self.trade_executor.update_position_marks(current_btc_price_for_marks)
                    settled_positions = self.trade_executor.check_and_settle_expired_options()
                
                # ML volatility model training
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

                # Regime detection model training
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

                # Sentiment analysis
                if self.sentiment_analyzer and hasattr(self.sentiment_analyzer, 'generate_sentiment_signal'):
                    try: 
                        self.sentiment_analyzer.generate_sentiment_signal()
                        logger.debug("Sentiment signal generated.")
                    except Exception as e: 
                        logger.debug(f"Sentiment analysis error: {e}")
                
                # Sleep for the configured interval
                await asyncio.sleep(getattr(config, 'ATTICUS_BACKGROUND_TASK_INTERVAL', 30))
                
            except asyncio.CancelledError:
                logger.info("AtticusBackend background task was cancelled.")
                break
            except Exception as e:
                logger.error(f"AtticusBackend background task error: {e}", exc_info=True)
                await asyncio.sleep(60)  # Wait longer on error
        
        logger.info("AtticusBackend: Background tasks finished.")

# Global reference for signal handler
backend_instance_for_shutdown: Optional[AtticusBackend] = None

def signal_handler_main_py(signum, frame):
    """Signal handler for graceful shutdown."""
    global backend_instance_for_shutdown
    logger.info(f"Main.py: Received signal {signum}, initiating AtticusBackend graceful shutdown...")
    logger.info("Main.py signal handler: backend stop will be managed by main() finally block.")

async def main():
    """Main function that runs both Uvicorn server and AtticusBackend logic concurrently."""
    global backend_instance_for_shutdown

    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler_main_py)
    signal.signal(signal.SIGTERM, signal_handler_main_py)

    # Ensure logs directory exists
    os.makedirs("logs", exist_ok=True)
    
    # Create AtticusBackend instance
    backend = AtticusBackend(app_instance=fastapi_app_instance)
    backend_instance_for_shutdown = backend 

    # Configure Uvicorn server
    uvicorn_config = uvicorn.Config(
        "backend.api:app",
        host=config.API_HOST,
        port=config.API_PORT,
        log_level=config.LOG_LEVEL.lower(), 
        reload=config.DEMO_MODE,
        lifespan="on"
    )
    server = uvicorn.Server(uvicorn_config)

    async def start_atticus_backend_logic_wrapper(backend_to_start):
        """Wrapper that waits for API startup before starting AtticusBackend."""
        logger.info("AtticusBackend logic waiting for API startup to complete...")
        try:
            await asyncio.wait_for(api_startup_complete_event.wait(), timeout=config.API_STARTUP_TIMEOUT)
            logger.info("API startup complete event received, starting AtticusBackend logic.")
            await backend_to_start.start()  # This now awaits the long-running background tasks
        except asyncio.TimeoutError:
            logger.error(f"Timeout waiting for API startup complete event after {config.API_STARTUP_TIMEOUT}s. AtticusBackend logic will not start.")
        except RuntimeError as e:
             logger.error(f"RuntimeError during AtticusBackend startup: {e}. AtticusBackend logic will not start.")
        except Exception as e:
            logger.error(f"Unexpected error starting AtticusBackend logic: {e}", exc_info=True)
    
    # Create and name the main tasks
    api_server_task = asyncio.create_task(server.serve())
    api_server_task.set_name("UvicornAPIServerTask")
    
    atticus_logic_task = asyncio.create_task(start_atticus_backend_logic_wrapper(backend))
    atticus_logic_task.set_name("AtticusBackendLogicTask")

    try:
        # Wait for either task to complete
        done, pending = await asyncio.wait(
            {api_server_task, atticus_logic_task}, 
            return_when=asyncio.FIRST_COMPLETED
        )
        
        # Log which task completed and if it had an error
        for task in done:
            task_name = task.get_name() if hasattr(task, 'get_name') else "Unknown Task"
            if task.exception():
                logger.error(f"Task '{task_name}' completed with an error: {task.exception()}", exc_info=task.exception())
            else:
                logger.info(f"Task '{task_name}' completed normally.")
        
        # Cancel pending tasks
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
        
        # Stop AtticusBackend if it's running
        if backend_instance_for_shutdown and backend_instance_for_shutdown.is_running:
            logger.info("Stopping AtticusBackend...")
            await backend_instance_for_shutdown.stop()
        else:
            logger.info("AtticusBackend was not running or already stopped/failed to start.")

        # Handle Uvicorn server shutdown
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
    try:
        asyncio.run(main())
    except Exception as e_outer_main:
        print(f"CRITICAL UNHANDLED ERROR in main asyncio.run: {e_outer_main}")
