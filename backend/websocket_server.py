# backend/websocket_server.py
import asyncio
import websockets # For the server
import json
import threading
import time

# Import your other backend modules
from backend import config # Your configuration file
from backend.utils import setup_logger # Your logging utility
from backend.coinbase_client import start_coinbase_ws, coinbase_btc_price_info
from backend.kraken_client import start_kraken_ws, kraken_btc_price_info
from backend.okx_client import start_okx_ws, okx_btc_price_info
from backend.dynamic_pricing import get_option_chain # Your option pricing logic

logger = setup_logger(__name__) # Initialize logger for this module

# --- Global State for Server ---
latest_platform_data = {
    "platform_btc_price": None,
    "wallet_balance": None,
    "platform_liquidity_percentage": None,
    "option_chain": [],
    "_internal_competitors": {
        "coinbase": {"bid": None, "ask": None, "price": None},
        "kraken": {"bid": None, "ask": None, "price": None},
        "okx": {"bid": None, "ask": None, "price": None},
    },
    "timestamp": None
}

CONNECTED_CLIENTS = set()

# --- Data Aggregation and Processing Background Task ---
async def data_aggregator_task():
    global latest_platform_data
    logger.info("Data aggregator task started.")
    while True:
        try:
            cb_last_trade = coinbase_btc_price_info.get('price')
            cb_bid = coinbase_btc_price_info.get('bid')
            cb_ask = coinbase_btc_price_info.get('ask')
            latest_platform_data["_internal_competitors"]["coinbase"] = {"bid": cb_bid, "ask": cb_ask, "price": cb_last_trade}

            kraken_last_trade = kraken_btc_price_info.get('price')
            kraken_bid = kraken_btc_price_info.get('bid')
            kraken_ask = kraken_btc_price_info.get('ask')
            latest_platform_data["_internal_competitors"]["kraken"] = {"bid": kraken_bid, "ask": kraken_ask, "price": kraken_last_trade}
            
            okx_bid = okx_btc_price_info.get('bid')
            okx_ask = okx_btc_price_info.get('ask')
            okx_last_trade = (okx_bid + okx_ask) / 2 if okx_bid and okx_ask else None
            latest_platform_data["_internal_competitors"]["okx"] = {"bid": okx_bid, "ask": okx_ask, "price": okx_last_trade}

            current_platform_price = None
            if cb_last_trade:
                current_platform_price = cb_last_trade
            elif cb_bid and cb_ask:
                current_platform_price = (cb_bid + cb_ask) / 2
            elif kraken_last_trade:
                current_platform_price = kraken_last_trade
            elif kraken_bid and kraken_ask:
                current_platform_price = (kraken_bid + kraken_ask) / 2
            elif okx_last_trade:
                current_platform_price = okx_last_trade
            elif latest_platform_data.get("platform_btc_price") is not None:
                current_platform_price = latest_platform_data["platform_btc_price"]
                logger.warning("All live price feeds seem down. Using last known platform price.")
            else:
                logger.error("No BTC price source available to calculate options.")

            if current_platform_price is not None:
                latest_platform_data["platform_btc_price"] = round(float(current_platform_price), 2)
                latest_platform_data["option_chain"] = get_option_chain(current_platform_price)
            else:
                latest_platform_data["platform_btc_price"] = None
                latest_platform_data["option_chain"] = []
                logger.warning("Option chain is empty as platform_btc_price is None.")

            simulated_wallet_balance = 0.5000 
            latest_platform_data["wallet_balance"] = float(simulated_wallet_balance)

            if latest_platform_data["platform_btc_price"]:
                base_liquidity = 70
                price_fluctuation_factor = (int(latest_platform_data["platform_btc_price"] * 100) % 20)
                simulated_liquidity = base_liquidity + price_fluctuation_factor - 10 
                latest_platform_data["platform_liquidity_percentage"] = max(20, min(95, int(simulated_liquidity)))
            else:
                latest_platform_data["platform_liquidity_percentage"] = 50

            latest_platform_data["timestamp"] = time.time()
            
            logger.debug(
                f"Data for Frontend: BTC Price: {latest_platform_data.get('platform_btc_price')}, "
                f"Wallet: {latest_platform_data.get('wallet_balance')}, "
                f"Liq %: {latest_platform_data.get('platform_liquidity_percentage')}, "
                f"Options: {len(latest_platform_data.get('option_chain', []))}"
            )

        except Exception as e:
            logger.error(f"CRITICAL Error in data_aggregator_task: {e}", exc_info=True)
        
        await asyncio.sleep(config.DATA_BROADCAST_INTERVAL_SECONDS / 2)

# --- WebSocket Server Broadcasting Logic ---
async def broadcast_data_to_clients():
    if CONNECTED_CLIENTS:
        data_to_send = {
            "platform_btc_price": latest_platform_data.get("platform_btc_price"),
            "wallet_balance": latest_platform_data.get("wallet_balance"),
            "platform_liquidity_percentage": latest_platform_data.get("platform_liquidity_percentage"),
            "option_chain": latest_platform_data.get("option_chain", []),
            "timestamp": latest_platform_data.get("timestamp")
        }

        if data_to_send["platform_btc_price"] is None and not data_to_send["option_chain"]:
             logger.debug("Skipping broadcast as critical data (BTC price/option chain) is missing.")
             return

        try:
            message_to_send = json.dumps(data_to_send)
        except Exception as e_json:
            logger.error(f"JSON DUMP FAILED for data: {data_to_send}", exc_info=True)
            return 
        
        send_tasks = [client.send(message_to_send) for client in CONNECTED_CLIENTS]
        results = await asyncio.gather(*send_tasks, return_exceptions=True)
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Failed to send message to a client: {result}")
    elif not CONNECTED_CLIENTS:
        logger.debug("No clients connected, skipping broadcast.")

async def periodic_broadcast_task():
    logger.info("Periodic broadcast task started.")
    while True:
        await broadcast_data_to_clients()
        await asyncio.sleep(config.DATA_BROADCAST_INTERVAL_SECONDS)

# --- WebSocket Server Connection Handler ---
async def connection_handler(websocket_connection): # Signature is correct (no 'path' argument)
    """
    Handles new WebSocket connections from frontend clients.
    Registers the client for broadcasts and handles disconnection.
    """
    client_address = websocket_connection.remote_address
    # Correct way to access path in newer 'websockets' library versions:
    request_path = websocket_connection.request.path # <<< CORRECTED ACCESS TO PATH
    
    logger.info(f"Client connected: {client_address} from path: {request_path}")
    CONNECTED_CLIENTS.add(websocket_connection)
    try:
        async for message_from_client in websocket_connection:
            logger.info(f"Received message from {client_address}: {message_from_client}")
            pass 
    except websockets.exceptions.ConnectionClosedOK:
        logger.info(f"Client disconnected gracefully: {client_address}")
    except websockets.exceptions.ConnectionClosedError as e:
        logger.warning(f"Client connection closed with error: {client_address} - {e}")
    except Exception as e: 
        logger.error(f"Error in connection_handler for {client_address}: {e}", exc_info=True)
    finally:
        if websocket_connection in CONNECTED_CLIENTS: 
            CONNECTED_CLIENTS.remove(websocket_connection)
        logger.info(f"Client removed: {client_address}. Total clients: {len(CONNECTED_CLIENTS)}")

# --- Main Function to Start Everything ---
async def main_server_startup():
    logger.info(f"Starting {config.PLATFORM_NAME} WebSocket Server on {config.WEBSOCKET_SERVER_HOST}:{config.WEBSOCKET_SERVER_PORT}")

    logger.info("Initializing exchange client threads...")
    threading.Thread(target=start_coinbase_ws, daemon=True, name="CoinbaseWSThread").start()
    threading.Thread(target=start_kraken_ws, daemon=True, name="KrakenWSThread").start()
    threading.Thread(target=start_okx_ws, daemon=True, name="OKXWSThread").start()

    logger.info("Waiting a few seconds for exchange clients to attempt connections...")
    await asyncio.sleep(10)

    logger.info("Starting internal data aggregation and broadcast tasks...")
    asyncio.create_task(data_aggregator_task())
    asyncio.create_task(periodic_broadcast_task())

    server_instance = await websockets.serve(
        connection_handler,
        config.WEBSOCKET_SERVER_HOST,
        config.WEBSOCKET_SERVER_PORT,
        ping_interval=20, 
        ping_timeout=20   
    )
    logger.info(f"WebSocket server listening on ws://{config.WEBSOCKET_SERVER_HOST}:{config.WEBSOCKET_SERVER_PORT}")
    
    await asyncio.Future() 


if __name__ == "__main__":
    try:
        asyncio.run(main_server_startup())
    except KeyboardInterrupt:
        logger.info(f"{config.PLATFORM_NAME} WebSocket server shutting down due to KeyboardInterrupt...")
    except Exception as e:
        logger.critical(f"{config.PLATFORM_NAME} WebSocket server failed to start or crashed: {e}", exc_info=True)
    finally:
        logger.info(f"{config.PLATFORM_NAME} WebSocket server has stopped.")
