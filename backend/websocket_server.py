# backend/websocket_server.py
import asyncio
import websockets # For the server
import json
import threading
import time

# Import your other backend modules
from backend import config # Your configuration file
from backend.utils import setup_logger # Your logging utility
from backend.coinbase_client import start_coinbase_ws, coinbase_btc_price_info # Revised Coinbase client
from backend.kraken_client import start_kraken_ws, kraken_btc_price_info # New Kraken client
from backend.okx_client import start_okx_ws, okx_btc_price_info # Your OKX client
from backend.dynamic_pricing import get_option_chain # Your option pricing logic

logger = setup_logger(__name__) # Initialize logger for this module

# --- Global State for Server ---
# This dictionary will hold the latest aggregated data to be broadcasted to clients.
latest_platform_data = {
    "platform_btc_price": None,      # Primary BTC price for your platform's options
    "platform_btc_bid": None,        # Primary bid
    "platform_btc_ask": None,        # Primary ask
    "option_chain": [],              # List of dynamically priced options
    "competitors": {                 # Data from competitor/hedging exchanges
        "kraken": {"bid": None, "ask": None, "price": None},
        "okx": {"bid": None, "ask": None, "price": None},
        # Add other competitors here if you include more clients
    },
    "timestamp": None                # Timestamp of the last data update
}

# A set to keep track of all currently connected frontend (Lovable) WebSocket clients.
CONNECTED_CLIENTS = set()

# --- Data Aggregation and Processing Background Task ---
async def data_aggregator_task():
    """
    Periodically fetches the latest data from the individual exchange client modules,
    calculates the dynamic option chain for your platform,
    and updates the global `latest_platform_data` state.
    This task runs continuously in the background.
    """
    global latest_platform_data
    logger.info("Data aggregator task started.")
    while True:
        try:
            # 1. Determine the primary BTC price for your platform
            # Priority: Coinbase last trade price, then Coinbase mid-price, then Kraken mid-price, then OKX mid-price
            current_platform_price = None
            cb_last_trade = coinbase_btc_price_info.get('price')
            cb_bid = coinbase_btc_price_info.get('bid')
            cb_ask = coinbase_btc_price_info.get('ask')

            kraken_bid = kraken_btc_price_info.get('bid')
            kraken_ask = kraken_btc_price_info.get('ask')
            # Use Kraken 'price' (last trade) if available, otherwise mid-price
            kraken_price_source = kraken_btc_price_info.get('price')
            if not kraken_price_source and kraken_bid and kraken_ask:
                 kraken_price_source = (kraken_bid + kraken_ask) / 2


            okx_bid = okx_btc_price_info.get('bid')
            okx_ask = okx_btc_price_info.get('ask')
            okx_price_source = None # OKX ticker might not have 'last trade' directly, so use mid
            if okx_bid and okx_ask:
                okx_price_source = (okx_bid + okx_ask) / 2


            if cb_last_trade:
                current_platform_price = cb_last_trade
                logger.debug(f"Using Coinbase last trade price for platform: ${current_platform_price:.2f}")
            elif cb_bid and cb_ask:
                current_platform_price = (cb_bid + cb_ask) / 2
                logger.debug(f"Using Coinbase mid-price for platform: ${current_platform_price:.2f}")
            elif kraken_price_source:
                current_platform_price = kraken_price_source
                logger.warning(f"Coinbase unavailable, using Kraken price as fallback: ${current_platform_price:.2f}")
            elif okx_price_source:
                current_platform_price = okx_price_source
                logger.warning(f"Coinbase & Kraken unavailable, using OKX price as fallback: ${current_platform_price:.2f}")
            else:
                logger.error("No reliable BTC price source available for platform pricing.")
                # Keep previous price if available, or set options to empty
                if latest_platform_data["platform_btc_price"] is None: # if it was never set
                    current_platform_price = None # Explicitly
                else: # Use the last known good price to avoid chain disappearing
                    current_platform_price = latest_platform_data["platform_btc_price"]


            # 2. Update platform price info
            if current_platform_price is not None:
                latest_platform_data["platform_btc_price"] = round(current_platform_price, 2)
                latest_platform_data["platform_btc_bid"] = cb_bid # Still reflects Coinbase's bid if available
                latest_platform_data["platform_btc_ask"] = cb_ask # Still reflects Coinbase's ask if available
                
                # 3. Generate dynamic option chain using the determined platform price
                option_chain = get_option_chain(current_platform_price) # From dynamic_pricing.py
                latest_platform_data["option_chain"] = option_chain
            else:
                latest_platform_data["option_chain"] = [] # No price, no options
                logger.warning("Option chain is empty due to no current platform BTC price.")


            # 4. Update competitor data
            latest_platform_data["competitors"]["kraken"]["bid"] = kraken_btc_price_info.get('bid')
            latest_platform_data["competitors"]["kraken"]["ask"] = kraken_btc_price_info.get('ask')
            latest_platform_data["competitors"]["kraken"]["price"] = kraken_btc_price_info.get('price')

            latest_platform_data["competitors"]["okx"]["bid"] = okx_btc_price_info.get('bid')
            latest_platform_data["competitors"]["okx"]["ask"] = okx_btc_price_info.get('ask')
            # OKX might not provide 'price' directly in ticker, use mid if needed for display
            if okx_bid and okx_ask:
                 latest_platform_data["competitors"]["okx"]["price"] = (okx_bid + okx_ask) / 2


            latest_platform_data["timestamp"] = time.time() # Record update time
            
            # logger.debug(f"Aggregated Data Snapshot: {json.dumps(latest_platform_data, indent=2)}")

        except Exception as e:
            logger.error(f"CRITICAL Error in data_aggregator_task: {e}", exc_info=True)
        
        # Pause before next aggregation cycle
        await asyncio.sleep(config.DATA_BROADCAST_INTERVAL_SECONDS / 2) # Aggregate slightly more often than broadcast

# --- WebSocket Server Broadcasting Logic ---
async def broadcast_data_to_clients():
    """
    Broadcasts the `latest_platform_data` to all currently connected frontend clients.
    This is called periodically by `periodic_broadcast_task`.
    """
    if CONNECTED_CLIENTS and latest_platform_data["platform_btc_price"] is not None: # Only broadcast if we have valid data
        message_to_send = json.dumps(latest_platform_data)
        
        # Create a list of tasks for sending the message to each client
        # This allows messages to be sent concurrently without blocking.
        send_tasks = [client.send(message_to_send) for client in CONNECTED_CLIENTS]
        
        # Wait for all send operations to complete (or fail)
        # return_exceptions=True ensures that if one send fails, others aren't cancelled.
        results = await asyncio.gather(*send_tasks, return_exceptions=True)
        
        # Log any errors that occurred during sending
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                # This part is tricky because CONNECTED_CLIENTS might change if a client disconnects
                # while we are iterating or preparing to log. For robust error handling on failed sends
                # and client removal, more sophisticated tracking might be needed.
                # For now, just log the error.
                logger.error(f"Failed to send message to a client: {result}")
    elif not CONNECTED_CLIENTS:
        logger.debug("No clients connected, skipping broadcast.")
    elif latest_platform_data["platform_btc_price"] is None:
        logger.debug("Platform BTC price is None, skipping broadcast.")


async def periodic_broadcast_task():
    """
    A background task that periodically calls `broadcast_data_to_clients`
    to send updates to the frontend.
    """
    logger.info("Periodic broadcast task started.")
    while True:
        await broadcast_data_to_clients()
        await asyncio.sleep(config.DATA_BROADCAST_INTERVAL_SECONDS)


# --- WebSocket Server Connection Handler ---
async def connection_handler(websocket_connection, path):
    """
    Handles new WebSocket connections from frontend clients.
    Registers the client for broadcasts and handles disconnection.
    """
    client_address = websocket_connection.remote_address
    logger.info(f"Client connected: {client_address}")
    CONNECTED_CLIENTS.add(websocket_connection)
    try:
        # Keep the connection alive and listen for any incoming messages (optional for now)
        # For this demo, it's primarily server-to-client data push.
        async for message_from_client in websocket_connection:
            logger.info(f"Received message from {client_address}: {message_from_client}")
            # Here you could handle client commands, e.g., trade requests in a real app
            # For example:
            # data = json.loads(message_from_client)
            # if data.get("action") == "place_trade":
            #     response = handle_trade_request(data)
            #     await websocket_connection.send(json.dumps(response))
            pass # No specific client-to-server messages handled in this basic version
    except websockets.exceptions.ConnectionClosedOK:
        logger.info(f"Client disconnected gracefully: {client_address}")
    except websockets.exceptions.ConnectionClosedError as e:
        logger.warning(f"Client connection closed with error: {client_address} - {e}")
    except Exception as e:
        logger.error(f"Error in connection_handler for {client_address}: {e}", exc_info=True)
    finally:
        # Ensure client is removed from the set upon disconnection
        CONNECTED_CLIENTS.remove(websocket_connection)
        logger.info(f"Client removed: {client_address}. Total clients: {len(CONNECTED_CLIENTS)}")


# --- Main Function to Start Everything ---
async def main_server_startup():
    """
    The main asynchronous function that initializes and starts all components:
    - Exchange WebSocket clients (in separate threads)
    - Data aggregation task
    - Periodic broadcasting task
    - The main WebSocket server for frontend connections
    """
    logger.info(f"Starting {config.PLATFORM_NAME} WebSocket Server on {config.WEBSOCKET_SERVER_HOST}:{config.WEBSOCKET_SERVER_PORT}")

    # Start individual exchange WebSocket clients in daemon threads.
    # Daemon threads will exit when the main program exits.
    # These functions (e.g., start_coinbase_ws) contain their own `run_forever()` loops.
    logger.info("Initializing exchange client threads...")
    threading.Thread(target=start_coinbase_ws, daemon=True, name="CoinbaseWSThread").start()
    threading.Thread(target=start_kraken_ws, daemon=True, name="KrakenWSThread").start()
    threading.Thread(target=start_okx_ws, daemon=True, name="OKXWSThread").start()

    # Allow some time for the exchange client threads to establish their connections
    logger.info("Waiting a few seconds for exchange clients to attempt connections...")
    await asyncio.sleep(10) # Adjust as needed

    # Start the asyncio background tasks for data processing and broadcasting
    logger.info("Starting internal data aggregation and broadcast tasks...")
    asyncio.create_task(data_aggregator_task())
    asyncio.create_task(periodic_broadcast_task())

    # Start the main WebSocket server that listens for frontend connections
    # The `websockets.serve` function returns a server object that runs until the Future is cancelled.
    server_instance = await websockets.serve(
        connection_handler,
        config.WEBSOCKET_SERVER_HOST,
        config.WEBSOCKET_SERVER_PORT,
        ping_interval=20, # Send pings to clients
        ping_timeout=20   # Timeout if pong not received
    )
    logger.info(f"WebSocket server listening on ws://{config.WEBSOCKET_SERVER_HOST}:{config.WEBSOCKET_SERVER_PORT}")
    
    # Keep the server running indefinitely (or until an interrupt)
    await asyncio.Future()


if __name__ == "__main__":
    try:
        # Run the main_server_startup coroutine using asyncio.run()
        asyncio.run(main_server_startup())
    except KeyboardInterrupt:
        logger.info(f"{config.PLATFORM_NAME} WebSocket server shutting down due to KeyboardInterrupt...")
    except Exception as e:
        logger.critical(f"{config.PLATFORM_NAME} WebSocket server failed to start or crashed: {e}", exc_info=True)
    finally:
        logger.info(f"{config.PLATFORM_NAME} WebSocket server has stopped.")
