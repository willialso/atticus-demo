# backend/websocket_server.py
import asyncio
import websockets
import json
import threading
import time

# Import your other backend modules
from backend import config
from backend.utils import setup_logger
from backend.coinbase_client import start_coinbase_ws, coinbase_btc_price_info
from backend.binance_client import start_binance_ws, binance_btc_price_info
from backend.okx_client import start_okx_ws, okx_btc_price_info
from backend.dynamic_pricing import get_option_chain, update_price_history # Assuming this updates a global price_history for vol calc

logger = setup_logger(__name__)

# --- Global State for Server ---
# This will hold the latest data to be broadcasted
latest_platform_data = {
    "platform_btc_price": None,
    "platform_btc_bid": None,
    "platform_btc_ask": None,
    "option_chain": [],
    "competitors": {
        "binance": {"bid": None, "ask": None},
        "okx": {"bid": None, "ask": None},
    },
    "timestamp": None
}

# Set of connected WebSocket clients (from frontend)
CONNECTED_CLIENTS = set()

# --- Data Aggregation and Processing Task ---
async def data_aggregator_task():
    """
    Periodically fetches data from exchange clients,
    calculates option chain, and updates `latest_platform_data`.
    """
    global latest_platform_data
    logger.info("Data aggregator task started.")
    while True:
        try:
            # Get platform's primary price from Coinbase
            cb_bid = coinbase_btc_price_info.get('bid')
            cb_ask = coinbase_btc_price_info.get('ask')
            cb_last = coinbase_btc_price_info.get('price')

            current_platform_price = None
            if cb_last:
                current_platform_price = cb_last
            elif cb_bid and cb_ask:
                current_platform_price = (cb_bid + cb_ask) / 2 # Mid-price if last trade not available

            if current_platform_price:
                latest_platform_data["platform_btc_price"] = round(current_platform_price, 2)
                latest_platform_data["platform_btc_bid"] = cb_bid
                latest_platform_data["platform_btc_ask"] = cb_ask
                
                # update_price_history for volatility calculation needs the current price.
                # dynamic_pricing.py needs to expose this or handle it internally if get_option_chain is called.
                # For simplicity here, let's assume get_option_chain handles the history update.
                # If not, you'd call: update_price_history(current_platform_price)
                
                option_chain = get_option_chain(current_platform_price) # From dynamic_pricing.py
                latest_platform_data["option_chain"] = option_chain
            else:
                # logger.warning("Coinbase price not available for platform pricing.")
                pass # Keep old data if new is not available

            # Get competitor prices
            latest_platform_data["competitors"]["binance"]["bid"] = binance_btc_price_info.get('bid')
            latest_platform_data["competitors"]["binance"]["ask"] = binance_btc_price_info.get('ask')
            latest_platform_data["competitors"]["okx"]["bid"] = okx_btc_price_info.get('bid')
            latest_platform_data["competitors"]["okx"]["ask"] = okx_btc_price_info.get('ask')

            latest_platform_data["timestamp"] = time.time()
            
            # logger.debug(f"Aggregated data: {json.dumps(latest_platform_data, indent=2)}")

        except Exception as e:
            logger.error(f"Error in data_aggregator_task: {e}", exc_info=True)
        
        await asyncio.sleep(config.DATA_BROADCAST_INTERVAL_SECONDS / 2) # Aggregate slightly more often than broadcast

# --- WebSocket Server Logic ---
async def broadcast_data():
    """Broadcasts `latest_platform_data` to all connected clients."""
    if CONNECTED_CLIENTS:
        message = json.dumps(latest_platform_data)
        # Create a list of tasks for sending messages
        tasks = [asyncio.create_task(client.send(message)) for client in CONNECTED_CLIENTS]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                # Potentially remove client if send fails repeatedly
                client_to_remove = list(CONNECTED_CLIENTS)[i] # Not perfectly safe if list changes
                logger.error(f"Failed to send message to {client_to_remove.remote_address}: {result}")


async def periodic_broadcast_task():
    """Periodically calls broadcast_data."""
    logger.info("Periodic broadcast task started.")
    while True:
        await broadcast_data()
        await asyncio.sleep(config.DATA_BROADCAST_INTERVAL_SECONDS)


async def handler(websocket, path):
    """Handles incoming WebSocket connections from clients."""
    logger.info(f"Client connected: {websocket.remote_address}")
    CONNECTED_CLIENTS.add(websocket)
    try:
        # Keep connection alive and listen for messages (optional for this demo)
        async for message in websocket:
            logger.info(f"Received message from {websocket.remote_address}: {message}")
            # Handle incoming messages if needed (e.g., client requests)
            # For this demo, primarily server-to-client push
            pass
    except websockets.exceptions.ConnectionClosedOK:
        logger.info(f"Client disconnected gracefully: {websocket.remote_address}")
    except websockets.exceptions.ConnectionClosedError as e:
        logger.warning(f"Client connection closed with error: {websocket.remote_address} - {e}")
    except Exception as e:
        logger.error(f"Error in handler for {websocket.remote_address}: {e}", exc_info=True)
    finally:
        CONNECTED_CLIENTS.remove(websocket)
        logger.info(f"Client removed: {websocket.remote_address}. Total clients: {len(CONNECTED_CLIENTS)}")


async def main_server():
    """Main function to start the WebSocket server and background tasks."""
    logger.info(f"Starting {config.PLATFORM_NAME} WebSocket Server on {config.WEBSOCKET_SERVER_HOST}:{config.WEBSOCKET_SERVER_PORT}")

    # Start exchange client WebSockets in separate threads
    # These are blocking calls (run_forever), so they need threads
    threading.Thread(target=start_coinbase_ws, daemon=True, name="CoinbaseWSThread").start()
    logger.info("Coinbase client thread starting...")
    threading.Thread(target=start_binance_ws, daemon=True, name="BinanceWSThread").start()
    logger.info("Binance client thread starting...")
    threading.Thread(target=start_okx_ws, daemon=True, name="OKXWSThread").start()
    logger.info("OKX client thread starting...")

    # Allow some time for exchange connections to establish
    logger.info("Waiting a few seconds for exchange clients to connect...")
    await asyncio.sleep(10) # Give time for on_open and initial messages

    # Start the asyncio tasks for data aggregation and broadcasting
    asyncio.create_task(data_aggregator_task())
    asyncio.create_task(periodic_broadcast_task())

    # Start the WebSocket server
    async with websockets.serve(handler, config.WEBSOCKET_SERVER_HOST, config.WEBSOCKET_SERVER_PORT):
        logger.info(f"WebSocket server listening on ws://{config.WEBSOCKET_SERVER_HOST}:{config.WEBSOCKET_SERVER_PORT}")
        await asyncio.Future()  # Run forever until interrupted

if __name__ == "__main__":
    try:
        asyncio.run(main_server())
    except KeyboardInterrupt:
        logger.info("WebSocket server shutting down...")
    except Exception as e:
        logger.critical(f"WebSocket server failed to start: {e}", exc_info=True)

